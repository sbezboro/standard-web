SET @rank=0;
insert into standardsurvival_veteranstatus (player_id, rank)
select player_id, @rank:=@rank+1 as rank from standardsurvival_playerstats where server_id = 1 order by time_spent desc