insert into standardsurvival_server
(id, name, address)
values (1, 'Standard Survival', 'standardsurvival.com');

insert into standardsurvival_playerstats
(player_id, server_id, time_spent, first_seen, last_seen, banned)
(select id, 1, time_spent, first_seen, last_seen, banned from standardsurvival_minecraftplayer);

alter table standardsurvival_minecraftplayer
drop time_spent,
drop first_seen,
drop last_seen,
drop last_login,
drop banned;

alter table `standardsurvival_serverstatus`
add column `server_id` integer NOT NULL,
add constraint `server_id_refs_id_67be644b` FOREIGN KEY (`server_id`) REFERENCES `standardsurvival_server` (`id`);

alter table `standardsurvival_killevent`
add column `server_id` integer NOT NULL,
add constraint `server_id_refs_id_6721235b` FOREIGN KEY (`server_id`) REFERENCES `standardsurvival_server` (`id`);

alter table `standardsurvival_deathevent`
add column `server_id` integer NOT NULL,
add constraint `server_id_refs_id_b5f7d8c4` FOREIGN KEY (`server_id`) REFERENCES `standardsurvival_server` (`id`);

update standardsurvival_serverstatus
set server_id = 1;
update standardsurvival_killevent
set server_id = 1;
update standardsurvival_deathevent
set server_id = 1;