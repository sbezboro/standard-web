var commandHistory = [];
var commandIndex = -1;

function Stream(sessionKey, baseUrl, $outputArea, $textbox, serverId, source) {
    var _this = this;
    
    this.sessionKey = sessionKey;
    this.baseUrl = baseUrl;
    this.$outputArea = $outputArea;
    this.$textbox = $textbox;
    this.serverId = serverId;
    this.source = source;
    this.socket = null;
    
    this.isAtBottom = function() {
        return $outputArea.get(0).scrollHeight - $outputArea.scrollTop() == $outputArea.outerHeight();
    }
    
    this.scrollToBottom = function() {
        $outputArea.scrollTop($outputArea.get(0).scrollHeight);
    }
    
    this.scrollToBottomIfAtBottom = function() {
        if (this.isAtBottom()) {
            this.scrollToBottom();
        }
    }
    
    this.addOutputLine = function(line) {
        var shouldScroll = _this.isAtBottom();
        
        $outputArea.append('<li>' + line + '</li>');
        
        // Scroll to see the new line of text if the bottom was already visible
        if (shouldScroll) {
            _this.scrollToBottom();
        }
    }
  
    this.addOutputLines = function(batch) {
        var shouldScroll = _this.isAtBottom();
        
        var html = "";
        batch.map(function(line) {
            html += '<li>' + line + '</li>';
        });
        
        $outputArea.append(html);
        
        // Scroll to see the new line of text if the bottom was already visible
        if (shouldScroll) {
            _this.scrollToBottom();
        }
    }
    
    this.messageEntered = function(input) {
        throw "Method should be implemented by inherited objects!";
    }
    
    this.socketInitialized = function() {
        throw "Method should be implemented by inherited objects!";
    }
    
    this.socketConnected = function() {
        throw "Method should be implemented by inherited objects!";
    }
    
    this.connect = function(callback) {
        this.addOutputLine("Connecting...");
        
        if (typeof io === 'undefined') {
            var msg = "ERROR: Server not reachable!";
            this.addOutputLine(msg);
            return callback(new Error(msg));
        }
        
        var socket = io.connect(this.baseUrl + '/' + this.source);
        this.socket = socket;
        
        _this.socketInitialized();
        
        socket.on('connect', function() {
            $outputArea.empty();
            _this.socketConnected();
        });
        
        socket.on('disconnect', function() {
            _rollbar.push({level: 'error', msg: 'Client disconnected from stream socket'});
            _this.addOutputLine("ERROR: socket connection lost!");
        });
        
        socket.on('mc-connection-lost', function() {
            _this.addOutputLine("Connection to Minecraft server lost, retrying...");
        });
        
        socket.on('mc-connection-restored', function() {
            _this.addOutputLine("Connection restored!");
        });
        
        $(document).keypress(function (e) {
            var focused = $(':focus');
            if ($textbox != focused
                && (!focused[0] || focused[0].type == false)) {
                $textbox.focus();
            }
        });
        
        $textbox.keyup(function(e) {
            switch (e.which) {
                case 13: //Enter
                    var input = $textbox.val();
                    
                    _this.messageEntered(input);
                    
                    $textbox.val("");
                    _this.scrollToBottom();
                    
                    commandHistory.unshift(input);
                    commandIndex = -1;
                    break;
                case 38: //Up
                    if (commandIndex < commandHistory.length - 1) {
                        commandIndex++;
                        $textbox.val(commandHistory[commandIndex]);
                    }
                    return false;
                case 40: //Down
                    if (commandIndex > -1) {
                        commandIndex--;
                        $textbox.val(commandHistory[commandIndex]);
                    }
                    return false;
            }
            
            return true;
        });
        
        return callback();
    }
}

function ConsoleStream(sessionKey, baseUrl, $outputArea, $textbox, serverId) {
    Stream.call(this, sessionKey, baseUrl, $outputArea, $textbox, serverId, 'console');
    this.allPlayers = {};
    this.onUpdate;
    
    var _this = this;
    var socket;
    
    $textbox.keyup(function(e) {
        if ($textbox.val().length >= 53) {
            $textbox.addClass('len-warn');
        } else {
            $textbox.removeClass('len-warn');
        }
    });
    
    this.socketInitialized = function() {
        socket = _this.socket;
        
        // This event is received when the session key is either invalid or doesn't
        // belong to a superuser
        socket.on('unauthorized', function(data) {
            _this.addOutputLine("ERROR: you are not authorized to access the admin panel!");
        });
        
        socket.on('console', function(data) {
            if (data.line) {
                _this.addOutputLine(data.line);
            } else if (data.batch) {
                _this.addOutputLines(data.batch);
            }
        });
        
        // Update server status display
        socket.on('server-status', function(data) {
            var players = data.players;
            var numPlayers = data.numPlayers;
            var maxPlayers = data.maxPlayers;
            var load = data.load;
            var tps = data.tps;
            
            players = players.sort(function(a, b) {
                a = (a.nickname ? a.nickname : a.username);
                b = (b.nickname ? b.nickname : b.username);
                
                if (a.toLowerCase() < b.toLowerCase()) return -1;
                if (a.toLowerCase() > b.toLowerCase()) return 1;
                return 0;
            });
            
            var playersHtml = '';
            for (var i = 0; i < players.length; ++i) {
                var username = players[i].username;
                _this.allPlayers[username] = players[i];
                
                var nicknameAnsi = players[i].nicknameAnsi;
                
                var displayName = nicknameAnsi ? nicknameAnsi : username;
                
                var html = ['<a href="#"><div class="player" username="' + username + '">',
                                '<img class="face-thumb" src="/faces/16/' + username + '.png"><span class="ansi-container">' + displayName + '</span>',
                                '<span class="rank">#' + players[i].rank + '</span>',
                            '</div></a>'].join('');
                
                playersHtml += html;
            }
            
            $('.players').html(playersHtml);
            $('.player-count').text(numPlayers + '/' + maxPlayers);
            $('.load').text(load);
            $('.tps').text(tps);
            
            if (_this.onUpdate && typeof _this.onUpdate === 'function') {
                _this.onUpdate();
            }
        });
        
        socket.on('chat-users', function(data) {
            var users = data.users;
            
            var html = '<b>Chat user count: ' + users.length + '</b>';
            for (var i = 0; i < users.length; ++i) {
                var username = users[i].username;
                var address = users[i].address;
                var type = users[i].type;
                
                if (username == 'Server') {
                    html += ['<div class="user">',
                                username + ' [' + type + ']',
                            '</div>'].join('');
                } else if (username) {
                    html += ['<div class="user">',
                                '<a href="/player/' + username + '">',
                                    '<span><img class="face-thumb" src="/faces/16/' + username + '.png">' + username + '</span>',
                                '</a>',
                            '</div>'].join('');
                } else {
                    html += ['<div class="user">',
                                'Anonymous - ' + address,
                            '</div>'].join('');
                }
            }
            
            $('.users').html(html);
        });
    }
    
    this.socketConnected = function() {
        socket.emit('auth', {
            djangoSessionKey: sessionKey,
            serverId: serverId
        });
    }
    
    this.messageEntered = function(input) {
        var data = {};
        
        if (input[0] == "/") {
            data = {
                command: input.substring(1, input.length)
            }
        } else {
            data = {
                message: input
            }
        }
        
        socket.emit('console-input', data);
        $textbox.removeClass('len-warn');
    }
    
    this.setDonator = function(username) {
        socket.emit('set-donator', {
            username: username
        });
    }
}

ConsoleStream.prototype = Object.create(Stream.prototype);

function ChatStream(sessionKey, baseUrl, $outputArea, $textbox, serverId) {
    Stream.call(this, sessionKey, baseUrl, $outputArea, $textbox, serverId, 'chat');
    var _this = this;
    var socket;
    
    this.socketInitialized = function() {
        socket = _this.socket;
        
        socket.on('connection-spam', function() {
            _this.addOutputLine("Stop trying to connect so much!");
            _this.addOutputLine("Try again in a few minutes...");
            _rollbar.push({level: 'info', msg: 'Connection spam blocked'});
        });
        
        socket.on('chat-spam', function() {
            _this.addOutputLine("Stop typing so fast!");
            _rollbar.push({level: 'info', msg: 'Chat spam blocked'});
        });
        
        socket.on('chat', function(data) {
            if (data.line) {
                _this.addOutputLine(data.line);
            } else if (data.batch) {
                _this.addOutputLines(data.batch);
            }
        });
        
        // Renders a table almost identical looking to the tab player table ingame
        socket.on('server-status', function(data) {
            var players = data.players;
            var numPlayers = data.numPlayers;
            var maxPlayers = data.maxPlayers;
            
            players = players.sort(function(a, b) {
                a = (a.nickname ? a.nickname : a.username);
                b = (b.nickname ? b.nickname : b.username);
                
                if (a.toLowerCase() < b.toLowerCase()) return -1;
                if (a.toLowerCase() > b.toLowerCase()) return 1;
                return 0;
            });
            
            var tableHtml = "<tr>";
            for (var i = 0; i < maxPlayers; ++i) {
                if (players.length <= i) {
                    tableHtml += '<td>&nbsp;</td>';
                } else {
                    var username = players[i].username;
                    var nickname = players[i].nickname;
                    
                    var displayName = (nickname ? nickname : username);
                    
                    tableHtml += ['<td>',
                                    '<a href="/player/' + username + '" target="_blank">',
                                      '<span><img class="face-thumb" src="/faces/16/' + username + '.png">' + displayName + '</span>',
                                    '</a>',
                                  '</td>'].join('');
                }
                
                // Three columns per row, same as ingame
                if ((i + 1) % 3 == 0) {
                    tableHtml += '</tr><tr>'
                }
            }
            tableHtml += "</tr>";
            
            $('.players-table').html(tableHtml);
        });
    }
    
    this.socketConnected = function() {
        var data = {
          serverId: serverId
        };
        
        if (sessionKey && sessionKey.length) {
            data['djangoSessionKey'] = sessionKey;
        }
        
        // Authenticate using the current django session key if it exists
        socket.emit('auth', data);
    }
    
    this.messageEntered = function(input) {
        socket.emit('chat-input', {
            message: input
        });
    }
}

ChatStream.prototype = Object.create(Stream.prototype);
