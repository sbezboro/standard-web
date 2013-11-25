import math
from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404, render, redirect
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db.models import Q, F, Sum
from django.utils.encoding import smart_str
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from djangobb_forum.util import build_form, convert_text_to_html, paginate, set_language
from djangobb_forum.models import Category, Forum, Topic, Post, Profile, Reputation,\
    Attachment, PostTracking
from djangobb_forum.forms import AddPostForm, EditPostForm, UserSearchForm,\
    PostSearchForm, ReputationForm, MailToForm, EssentialsProfileForm,\
    PersonalProfileForm, MessagingProfileForm, PersonalityProfileForm,\
    DisplayProfileForm, PrivacyProfileForm, ReportForm, UploadAvatarForm
from djangobb_forum.templatetags import forum_extras
from djangobb_forum import settings as forum_settings
from djangobb_forum.util import smiles, convert_text_to_html, TopicFromPostResult
from djangobb_forum.templatetags.forum_extras import forum_moderated_by

from haystack.query import SearchQuerySet, SQ

from standardweb import settings


def index(request, full=True):
    users_cached = cache.get('djangobb_users_online', {})
    users_online = users_cached and User.objects.filter(id__in = users_cached.keys()) or []
    guests_cached = cache.get('djangobb_guests_online', {})
    guest_count = len(guests_cached)
    users_count = len(users_online)

    cats = {}
    forums = {}
    user_groups = request.user.groups.all()
    if request.user.is_anonymous():  # in django 1.1 EmptyQuerySet raise exception
        user_groups = []
    _forums = Forum.objects.filter(
            Q(category__groups__in=user_groups) | \
            Q(category__groups__isnull=True)).select_related('last_post__topic',
                                                            'last_post__user',
                                                            'category',
                                                            'last_post__user__forum_profile__player')

    for forum in _forums:
        cat = cats.setdefault(forum.category.id,
            {'id': forum.category.id, 'cat': forum.category, 'forums': []})
        cat['forums'].append(forum)
        forums[forum.id] = forum

    cmpdef = lambda a, b: cmp(a['cat'].position, b['cat'].position)
    cats = sorted(cats.values(), cmpdef)

    to_return = {'cats': cats,
                'posts': Post.objects.filter(deleted=False).count(),
                'topics': Topic.objects.filter(deleted=False).count(),
                'users': User.objects.count(),
                'users_online': users_online,
                'online_count': users_count,
                'guest_count': guest_count,
                }
    if full:
        return render(request, 'djangobb_forum/index.html', to_return)
    else:
        return render(request, 'djangobb_forum/lofi/index.html', to_return)


@transaction.commit_on_success
def moderate(request, forum_id):
    forum = get_object_or_404(Forum, pk=forum_id)
    topics = forum.topics.filter(deleted=False).order_by('-sticky', '-updated').select_related()
    if request.user.is_superuser or request.user in forum.moderators.all():
        topic_ids = request.POST.getlist('topic_id')
        if 'move_topics' in request.POST:
            return render(request,  'djangobb_forum/move_topic.html', {
                'categories': Category.objects.all(),
                'topic_ids': topic_ids,
                'exclude_forum': forum,
            })
        elif 'delete_topics' in request.POST:
            for topic_id in topic_ids:
                topic = get_object_or_404(Topic, pk=topic_id)
                #topic.delete()
            return HttpResponseRedirect(reverse('djangobb:index'))
        elif 'open_topics' in request.POST:
            for topic_id in topic_ids:
                open_close_topic(request, topic_id, 'o')
            return HttpResponseRedirect(reverse('djangobb:index'))
        elif 'close_topics' in request.POST:
            for topic_id in topic_ids:
                open_close_topic(request, topic_id, 'c')
            return HttpResponseRedirect(reverse('djangobb:index'))

        return render(request, 'djangobb_forum/moderate.html', {'forum': forum,
                'topics': topics,
                #'sticky_topics': forum.topics.filter(sticky=True),
                'posts': forum.posts.filter(deleted=False).count(),
                })
    else:
        raise Http404


def search(request):
    # TODO: move to form
    if 'action' in request.GET:
        action = request.GET['action']
        #FIXME: show_user for anonymous raise exception, 
        #django bug http://code.djangoproject.com/changeset/14087 :|
        groups = request.user.groups.all() or [] #removed after django > 1.2.3 release
        topics = Topic.objects.filter(deleted=False).filter(
                   Q(forum__category__groups__in=groups) | \
                   Q(forum__category__groups__isnull=True))
        if action == 'show_24h':
            date = datetime.today() - timedelta(1)
            topics = topics.filter(created__gte=date)
        elif action == 'show_new':
            try:
                last_read = PostTracking.objects.get(user=request.user).last_read
            except PostTracking.DoesNotExist:
                last_read = None
            if last_read:
                topics = topics.filter(last_post__updated__gte=last_read).all()
            else:
                #searching more than forum_settings.SEARCH_PAGE_SIZE in this way - not good idea :]
                topics = [topic for topic in topics[:forum_settings.SEARCH_PAGE_SIZE] if forum_extras.has_unreads(topic, request.user)]
        elif action == 'show_unanswered':
            topics = topics.filter(post_count=1)
        elif action == 'show_subscriptions':
            topics = topics.filter(subscribers__id=request.user.id)
        elif action == 'show_user':
            user_id = request.GET['user_id']
            posts = Post.objects.filter(deleted=False, user__id=user_id)
            topics = [post.topic for post in posts if post.topic in topics]
        elif action == 'search':
            keywords = request.GET.get('keywords')
            author = request.GET.get('author')
            forum = request.GET.get('forum')
            search_in = request.GET.get('search_in')
            sort_by = request.GET.get('sort_by')
            sort_dir = request.GET.get('sort_dir')

            if not (keywords or author):
                return HttpResponseRedirect(reverse('djangobb:search'))

            query = SearchQuerySet().models(Post).filter(deleted=0)

            if author:
                query = query.filter(author__username=author)

            if forum != u'0':
                query = query.filter(forum__id=forum)

            if keywords:
                if search_in == 'all':
                    query = query.filter(SQ(topic=keywords) | SQ(text=keywords))
                elif search_in == 'message':
                    query = query.filter(text=keywords)
                elif search_in == 'topic':
                    query = query.filter(topic=keywords)

            # add exlusions for categories user does not have access too
            for category in Category.objects.all():
                if not category.has_access(request.user):
                    query = query.exclude(category=category)

            order = {'0': 'created',
                     '1': 'author',
                     '2': 'topic',
                     '3': 'forum'}.get(sort_by, 'created')
            if sort_dir == 'DESC':
                order = '-' + order

            posts = query.order_by(order)

            if 'topics' in request.GET['show_as']:
                return render(request, 'djangobb_forum/search_topics.html', {
                    'results': TopicFromPostResult(posts)
                })
            elif 'posts' in request.GET['show_as']:
                return render(request, 'djangobb_forum/search_posts.html', {'results': posts})

        return render(request, 'djangobb_forum/search_topics.html', {'results': topics})
    else:
        form = PostSearchForm()
        return render(request, 'djangobb_forum/search_form.html', {'categories': Category.objects.all(),
                'form': form,
                })


@login_required
def misc(request):
    if 'action' in request.GET:
        action = request.GET['action']
        if action =='markread':
            user = request.user
            PostTracking.objects.filter(user__id=user.id).update(last_read=datetime.now(), topics=None)
            return HttpResponseRedirect(reverse('djangobb:index'))

        elif action == 'report':
            if request.GET.get('post_id', ''):
                post_id = request.GET['post_id']
                post = get_object_or_404(Post, id=post_id)
                form = build_form(ReportForm, request, reported_by=request.user, post=post_id)
                if request.method == 'POST' and form.is_valid():
                    form.save()
                    return HttpResponseRedirect(post.get_absolute_url())
                return render(request, 'djangobb_forum/report.html', {'form':form})

    elif 'submit' in request.POST and 'mail_to' in request.GET:
        form = MailToForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = get_object_or_404(User, username=request.GET['mail_to'])
            subject = form.cleaned_data['subject']
            
            from_email = request.user.email or email
            
            if not from_email or '@' not in from_email:
                form.errors['email'] = 'Please enter a valid email address!'
                
                return render(request, 'djangobb_forum/mail_to.html', {
                    'form': form
                })
            
            if not request.user.email:
                request.user.email = from_email
                request.user.save()
            
            body_html = convert_text_to_html(form.cleaned_data['body'], 'bbcode')
            
            body = '%s<br><br><hr>Sent by <b>%s</b> on the Standard Survival Forum<br>%s' \
                   % (body_html, request.user.username, Site.objects.get_current().domain)
            
            message = EmailMessage(subject, body,
                '%s <%s>' % (request.user.username, settings.DEFAULT_FROM_EMAIL),
                [user.email], bcc=[settings.DEFAULT_FROM_EMAIL],
                headers={'Reply-To': from_email})
            message.content_subtype = 'html'
            message.send()
            
            return HttpResponseRedirect(reverse('djangobb:index'))

    elif 'mail_to' in request.GET:
        mailto = get_object_or_404(User, username=request.GET['mail_to'])
        form = MailToForm()
        return render(request, 'djangobb_forum/mail_to.html', {'form':form,
                'mailto': mailto}
                )


def show_forum(request, forum_id, full=True):
    forum = get_object_or_404(Forum, pk=forum_id)
    if not forum.category.has_access(request.user):
        return HttpResponseForbidden()

    topics = forum.topics.filter(deleted=False).select_related('user__forum_profile__player',
                                                               'last_post__user__forum_profile')
    
    if forum.locked:
        topics = topics.order_by('-sticky', '-created')
    else:
        topics = topics.order_by('-sticky', '-updated')

    moderator = request.user.is_superuser or\
        request.user in forum.moderators.all()
    to_return = {'categories': Category.objects.all(),
                'forum': forum,
                'posts': forum.post_count,
                'topics': topics,
                'moderator': moderator,
                }
    if full:
        return render(request, 'djangobb_forum/forum.html', to_return)
    else:
        return render(request, 'djangobb_forum/lofi/forum.html', to_return)


@transaction.commit_on_success
def show_topic(request, topic_id, full=True):
    topic = get_object_or_404(Topic.objects.filter(deleted=False).select_related(), pk=topic_id)
    if not topic.forum.category.has_access(request.user):
        return HttpResponseForbidden()
    Topic.objects.filter(deleted=False, pk=topic.id).update(views=F('views') + 1)

    last_post = topic.last_post

    if request.user.is_authenticated():
        topic.update_read(request.user)
    posts = topic.posts.filter(deleted=False) \
        .select_related('user__forum_profile__player') \
        .prefetch_related('attachments')

    initial = {}
    if request.user.is_authenticated():
        initial = {'markup': request.user.forum_profile.markup}
    form = AddPostForm(topic=topic, initial=initial)

    moderator = request.user.is_superuser or\
        request.user in topic.forum.moderators.all()
    if request.user.is_authenticated() and request.user in topic.subscribers.all():
        subscribed = True
    else:
        subscribed = False

    highlight_word = request.GET.get('hl', '')
    if full:
        return render(request, 'djangobb_forum/topic.html', {'categories': Category.objects.all(),
                'topic': topic,
                'last_post': last_post,
                'form': form,
                'moderator': moderator,
                'subscribed': subscribed,
                'posts': posts,
                'highlight_word': highlight_word,
                })
    else:
        return render(request, 'djangobb_forum/lofi/topic.html', {'categories': Category.objects.all(),
                'topic': topic,
                'posts': posts,
                })


@login_required
@transaction.commit_on_success
def add_post(request, forum_id, topic_id):
    from standardweb.lib import api
    
    if not request.user.is_active:
        raise PermissionDenied
    
    forum = None
    topic = None
    posts = None
    
    if forum_id:
        forum = get_object_or_404(Forum, pk=forum_id)
        if not forum.category.has_access(request.user):
            return HttpResponseForbidden()
        
        if not request.user.is_superuser and forum.locked:
            return HttpResponseForbidden()
        
    elif topic_id:
        topic = get_object_or_404(Topic, pk=topic_id, deleted=False)
        posts = topic.posts.filter(deleted=False).select_related()
        
        if not topic.forum.category.has_access(request.user):
            return HttpResponseForbidden()
        
    if topic and topic.closed:
        return HttpResponseRedirect(topic.get_absolute_url())

    ip = request.META.get('REMOTE_ADDR', None)
    form = build_form(AddPostForm, request, topic=topic, forum=forum,
                      user=request.user, ip=ip,
                      initial={'markup': request.user.forum_profile.markup})

    if 'post_id' in request.GET:
        post_id = request.GET['post_id']
        post = get_object_or_404(Post, pk=post_id)
        form.fields['body'].initial = u"[quote=%s]%s[/quote]" % (post.user, post.body)

    if form.is_valid():
        post = form.save();
        
        api.forum_post(request.user.username,
                       post.topic.forum.name,
                       post.topic.name,
                       post.get_absolute_url())
        
        return HttpResponseRedirect(post.get_absolute_url())

    return render(request, 'djangobb_forum/add_post.html', {'form': form,
            'posts': posts,
            'topic': topic,
            'forum': forum,
            })


@transaction.commit_on_success
def upload_avatar(request, username, template=None, form_class=None):
    user = get_object_or_404(User, username=username)
    if request.user.is_authenticated() and user == request.user or request.user.is_superuser:
        form = build_form(form_class, request, instance=user.forum_profile)
        if request.method == 'POST' and form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('djangobb:forum_profile', args=[user.username]))
        return render(request, template, {'form': form,
                'avatar_width': forum_settings.AVATAR_WIDTH,
                'avatar_height': forum_settings.AVATAR_HEIGHT,
               })
    else:
        topic_count = Topic.objects.filter(deleted=False, user__id=user.id).count()
        if user.forum_profile.post_count < forum_settings.POST_USER_SEARCH and not request.user.is_authenticated():
            return HttpResponseRedirect(reverse('user_signin') + '?next=%s' % request.path)
        return render(request, template, {'profile': user,
                'topic_count': topic_count,
               })


@transaction.commit_on_success
def user(request, username, section='essentials', action=None, template='djangobb_forum/profile/profile_essentials.html', form_class=EssentialsProfileForm):
    user = get_object_or_404(User, username=username)
    if request.user.is_authenticated() and user == request.user or request.user.is_superuser:
        profile_url = reverse('djangobb:forum_profile_%s' % section, args=[user.username])
        form = build_form(form_class, request, instance=user.forum_profile, extra_args={'request': request})
        if request.method == 'POST' and form.is_valid():
            form.save()
            return HttpResponseRedirect(profile_url)
        return render(request, template, {'active_menu': section,
                'profile': user,
                'form': form,
               })
    else:
        return HttpResponseRedirect('/player/%s' % username)


@login_required
@transaction.commit_on_success
def reputation(request, username):
    user = get_object_or_404(User, username=username)
    form = build_form(ReputationForm, request, from_user=request.user, to_user=user)

    if 'action' in request.GET:
        if request.user == user:
            return HttpResponseForbidden(u'You can not change the reputation of yourself')

        if 'post_id' in request.GET:
            post_id = request.GET['post_id']
            form.fields['post'].initial = post_id
            if request.GET['action'] == 'plus':
                form.fields['sign'].initial = 1
            elif request.GET['action'] == 'minus':
                form.fields['sign'].initial = -1
            return render(request, 'djangobb_forum/reputation_form.html', {'form': form})
        else:
            raise Http404

    elif request.method == 'POST':
        if 'del_reputation' in request.POST and request.user.is_superuser:
            reputation_list = request.POST.getlist('reputation_id')
            for reputation_id in reputation_list:
                    reputation = get_object_or_404(Reputation, pk=reputation_id)
                    reputation.delete()
            return HttpResponseRedirect(reverse('djangobb:index'))
        elif form.is_valid():
            form.save()
            post_id = request.POST['post']
            post = get_object_or_404(Post, id=post_id)
            return HttpResponseRedirect(post.get_absolute_url())
        else:
            return render(request, 'djangobb_forum/reputation_form.html', {'form': form})
    else:
        reputations = Reputation.objects.filter(to_user__id=user.id).order_by('-time').select_related()
        return render(request, 'djangobb_forum/reputation.html', {'reputations': reputations,
                'profile': user.forum_profile,
               })


def show_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    count = post.topic.posts.filter(deleted=False, created__lt=post.created).count() + 1
    page = math.ceil(count / float(forum_settings.TOPIC_PAGE_SIZE))
    url = '%s?page=%d#post-%d' % (reverse('djangobb:topic', args=[post.topic.id]), page, post.id)
    return HttpResponseRedirect(url)


@login_required
@transaction.commit_on_success
def edit_post(request, post_id):
    from djangobb_forum.templatetags.forum_extras import forum_editable_by

    post = get_object_or_404(Post, pk=post_id)
    topic = post.topic
    if not forum_editable_by(post, request.user):
        return HttpResponseRedirect(post.get_absolute_url())
    form = build_form(EditPostForm, request, topic=topic, instance=post)
    if form.is_valid():
        post = form.save(commit=False)
        post.updated_by = request.user
        post.save()
        return HttpResponseRedirect(post.get_absolute_url())

    return render(request, 'djangobb_forum/edit_post.html', {'form': form,
            'post': post,
            })


@login_required
@transaction.commit_on_success
def delete_posts(request, topic_id):

    topic = Topic.objects.select_related().get(pk=topic_id)

    if forum_moderated_by(topic, request.user):
        deleted = False
        post_list = request.POST.getlist('post')
        for post_id in post_list:
            if not deleted:
                deleted = True
            delete_post(request, post_id)
        if deleted:
            return HttpResponseRedirect(topic.get_absolute_url())

    last_post = topic.posts.filter(deleted=False).latest()

    if request.user.is_authenticated():
        topic.update_read(request.user)

    posts = topic.posts.filter(deleted=False).select_related()

    initial = {}
    if request.user.is_authenticated():
        initial = {'markup': request.user.forum_profile.markup}
    form = AddPostForm(topic=topic, initial=initial)

    moderator = request.user.is_superuser or\
        request.user in topic.forum.moderators.all()
    if request.user.is_authenticated() and request.user in topic.subscribers.all():
        subscribed = True
    else:
        subscribed = False
    return render(request, 'djangobb_forum/delete_posts.html', {
            'topic': topic,
            'last_post': last_post,
            'form': form,
            'moderator': moderator,
            'subscribed': subscribed,
            'posts': posts,
            })


@login_required
@transaction.commit_on_success
def move_topic(request):
    if 'topic_id' in request.GET:
        #if move only 1 topic
        topic_ids = [request.GET['topic_id']]
    else:
        topic_ids = request.POST.getlist('topic_id')
    first_topic = topic_ids[0]
    topic = get_object_or_404(Topic, pk=first_topic)
    from_forum = topic.forum
    if 'to_forum' in request.POST:
        to_forum_id = int(request.POST['to_forum'])
        to_forum = get_object_or_404(Forum, pk=to_forum_id)
        for topic_id in topic_ids:
            topic = get_object_or_404(Topic, pk=topic_id)
            if topic.forum != to_forum:
                if forum_moderated_by(topic, request.user):
                    topic.forum = to_forum
                    topic.save()

        #TODO: not DRY
        try:
            last_post = Post.objects.filter(deleted=False, topic__forum__id=from_forum.id).latest()
        except Post.DoesNotExist:
            last_post = None
        from_forum.last_post = last_post
        from_forum.topic_count = from_forum.topics.filter(deleted=False).count()
        from_forum.post_count = from_forum.posts.filter(deleted=False).count()
        from_forum.save()
        return HttpResponseRedirect(to_forum.get_absolute_url())

    return render(request, 'djangobb_forum/move_topic.html', {'categories': Category.objects.all(),
            'topic_ids': topic_ids,
            'exclude_forum': from_forum,
            })


@login_required
@transaction.commit_on_success
def stick_unstick_topic(request, topic_id, action):

    topic = get_object_or_404(Topic, pk=topic_id)
    if forum_moderated_by(topic, request.user):
        if action == 's':
            topic.sticky = True
        elif action == 'u':
            topic.sticky = False
        topic.save()
    return HttpResponseRedirect(topic.get_absolute_url())


@login_required
@transaction.commit_on_success
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    last_post = post.topic.last_post
    topic = post.topic
    forum = post.topic.forum

    allowed = False
    if request.user.is_superuser or\
        request.user in post.topic.forum.moderators.all() or \
        (post.user == request.user and post == last_post):
        allowed = True

    if not allowed:
        return HttpResponseRedirect(post.get_absolute_url())

    post.delete()

    try:
        Topic.objects.get(deleted=False, pk=topic.id)
    except Topic.DoesNotExist:
        #removed latest post in topic
        return HttpResponseRedirect(forum.get_absolute_url())
    else:
        return HttpResponseRedirect(topic.get_absolute_url())


@login_required
@transaction.commit_on_success
def open_close_topic(request, topic_id, action):

    topic = get_object_or_404(Topic, pk=topic_id)
    if forum_moderated_by(topic, request.user):
        if action == 'c':
            topic.closed = True
        elif action == 'o':
            topic.closed = False
        topic.save()
    return HttpResponseRedirect(topic.get_absolute_url())


def users(request):
    users = User.objects.filter(forum_profile__post_count__gte=forum_settings.POST_USER_SEARCH).order_by('username')
    form = UserSearchForm(request.GET)
    users = form.filter(users)
    return render(request, 'djangobb_forum/users.html', {'users': users,
            'form': form,
            })


@login_required
@transaction.commit_on_success
def delete_subscription(request, topic_id):
    topic = get_object_or_404(Topic, pk=topic_id)
    topic.subscribers.remove(request.user)
    if 'from_topic' in request.GET:
        return HttpResponseRedirect(reverse('djangobb:topic', args=[topic.id]))
    else:
        return HttpResponseRedirect(reverse('djangobb:forum_profile', args=[request.user.username]))


@login_required
@transaction.commit_on_success
def add_subscription(request, topic_id):
    topic = get_object_or_404(Topic, pk=topic_id)
    topic.subscribers.add(request.user)
    return HttpResponseRedirect(reverse('djangobb:topic', args=[topic.id]))


def show_attachment(request, hash):
    attachment = get_object_or_404(Attachment, hash=hash)
    file_data = file(attachment.get_absolute_path(), 'rb').read()
    response = HttpResponse(file_data, mimetype=attachment.content_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % smart_str(attachment.name)
    return response


@login_required
@csrf_exempt
def post_preview(request):
    '''Preview for markitup'''
    markup = request.user.forum_profile.markup
    data = request.POST.get('data', '')

    data = convert_text_to_html(data, markup)
    if forum_settings.SMILES_SUPPORT:
        data = smiles(data)
    return render(request, 'djangobb_forum/post_preview.html', {'data': data})

@login_required
def signout(request):
    logout(request)
    return redirect(reverse('djangobb:index'))

def register(request):
    return render(request, 'djangobb_forum/register.html')