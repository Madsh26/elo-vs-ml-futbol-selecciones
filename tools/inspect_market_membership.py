"""Inspect dated national-team lineups without reading match scores."""
import duckdb
connection=duckdb.connect('data/raw/transfermarkt.duckdb',read_only=True)
print(connection.execute("""SELECT nt.name,min(l.date),max(l.date),count(*),count(distinct l.player_id)
 FROM game_lineups l JOIN national_teams nt ON CAST(l.club_id AS VARCHAR)=nt.national_team_id
 WHERE l.date < DATE '2026-06-10' GROUP BY nt.name ORDER BY nt.name""").fetchall())
print(connection.execute('DESCRIBE games').fetchall())
print(connection.execute("""SELECT l.date,nt.name,l.type,l.position,g.competition_id,g.home_club_id,g.away_club_id
 FROM game_lineups l JOIN national_teams nt ON CAST(l.club_id AS VARCHAR)=nt.national_team_id
 JOIN games g ON l.game_id=g.game_id WHERE l.date < DATE '2026-06-10' LIMIT 6""").fetchall())
