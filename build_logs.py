import requests
import datetime
import calendar
import sqlite3
from pathlib import Path


def main():
    setup_db()
    build_yearly_gamelogs("2021")
    #build_monthly_gamelogs("2020","12")
    #build_daily_gamelogs("2014-01-08")

def setup_db():
    
    filepath = Path(__file__).parent
    con = sqlite3.connect(filepath / "gamelogs.db")
    cur = con.cursor()

    # Create tables
    cur.execute('''CREATE TABLE IF NOT EXISTS batting
                (game_date text, game_id integer, game_type text, venue_id integer, league_id integer,
                 player_id integer, batting_order text, AB integer, R integer, H integer,
                "2B" integer, "3B" integer, HR integer, RBI integer, SB integer, CS integer, BB integer,
                SO integer, IBB integer, HBP integer, SH integer, SF integer, GIDP integer)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS pitching
                (game_date text, game_id integer, game_type text, venue_id integer, league_id integer,
                 player_id integer, W integer, L integer, G integer, GS integer, CG integer,
                 SHO integer, QS integer, SV integer, HLD integer, BFP integer, IP real,
                 H integer, ER integer, R integer, HR integer, SO integer, BB integer, IBB integer,
                 HBP integer, WP integer, BK integer)''')
    
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_game_batter ON batting (game_id, player_id);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_game_pitcher ON pitching (game_id, player_id);")
    con.close()


def build_yearly_gamelogs(year):


    months = ["01","02","03","04","05","06","07","08","09","10","11","12"]

    for month in months:
        build_monthly_gamelogs(year, month)


def build_monthly_gamelogs(year, month):

    # Get a list of days in the month
    num_days = calendar.monthrange(int(year), int(month))[1]
    game_dates = [datetime.date(int(year), int(month), day) for day in range(1, num_days + 1)]

    for game_date in game_dates:
        build_daily_gamelogs(game_date.strftime("%Y-%m-%d"))


def build_daily_gamelogs(date_string):

    games = []
        
    print(date_string)
     # Get a list of game ids for games on this date
    games = get_games(date_string)

    filepath = Path(__file__).parent
    con = sqlite3.connect(filepath / "gamelogs.db")
    cur = con.cursor()

    # For each game, get the stats for every player
    for game in games:
        game_batting, game_pitching = get_game_logs(game)

        # Insert into DB
        for row in game_batting:
            cur.execute('''REPLACE INTO batting VALUES
                        (:game_date, :game_id, :game_type, :venue_id, :league_id,
                         :player_id, :batting_order, :AB, :R, :H, :2B, :3B, 
                         :HR, :RBI, :SB, :CS, :BB, :SO, :IBB, :HBP, :SH,
                         :SF, :GIDP)''', row)
        
        for row in game_pitching:
            cur.execute('''REPLACE INTO pitching VALUES
                        (:game_date, :game_id, :game_type, :venue_id, :league_id,
                         :player_id, :W, :L, :G, :GS, :CG, :SHO, :QS, :SV, 
                         :HLD, :BFP, :IP, :H, :ER, :R, :HR, :SO, :BB, :IBB,
                         :HBP, :WP, :BK)''', row)
        
    
    con.commit()
    con.close()



def get_games(date_string):

    games = []
    sportIds = [1, 11, 12, 13, 14, 16, 17]

    for sportId in sportIds:
        url = "https://statsapi.mlb.com/api/v1/schedule/?sportId={}&date={}".format(
            sportId,
            date_string
        )
        schedule = requests.get(url).json()

        for date in schedule["dates"]:
            for game_data in date["games"]:
                # Skip games that are not finished ("F")
                # If a game was delayed, it will show up again on a later calendar date
                if game_data["status"]["codedGameState"] == "F":
                    game = {}
                    game["date"] = date_string
                    game["game_id"] = game_data["gamePk"]
                    game["game_type"] = game_data["gameType"]
                    game["venue_id"] = game_data["venue"]["id"]
                    game["league_id"] = sportId
                    games.append(game)

    return games


def get_game_logs(game):

    batting_logs = []
    pitching_logs = []
    url = "https://statsapi.mlb.com/api/v1/game/{}/boxscore".format(game["game_id"])
    game_info = requests.get(url).json()

    print(game["game_id"])
    if "teams" in game_info:
        for team in game_info["teams"].values():
            for player in team["players"].values():
                if player["stats"]["batting"]:
                    batting_log = {}
                    batting_log["game_date"] = game["date"]
                    batting_log["game_id"] = int(game["game_id"])
                    batting_log["game_type"] = game["game_type"]
                    batting_log["venue_id"] = int(game["venue_id"])
                    batting_log["league_id"] = int(game["league_id"])
                    batting_log["player_id"] = int(player["person"]["id"])
                    batting_log["batting_order"] = player.get("battingOrder", "")
                    batting_log["AB"] = int(player["stats"]["batting"]["atBats"])
                    batting_log["R"] = int(player["stats"]["batting"]["runs"])
                    batting_log["H"] = int(player["stats"]["batting"]["hits"])
                    batting_log["2B"] = int(player["stats"]["batting"]["doubles"])
                    batting_log["3B"] = int(player["stats"]["batting"]["triples"])
                    batting_log["HR"] = int(player["stats"]["batting"]["homeRuns"])
                    batting_log["RBI"] = int(player["stats"]["batting"]["rbi"])
                    batting_log["SB"] = int(player["stats"]["batting"]["stolenBases"])
                    batting_log["CS"] = int(player["stats"]["batting"]["caughtStealing"])
                    batting_log["BB"] = int(player["stats"]["batting"]["baseOnBalls"])
                    batting_log["SO"] = int(player["stats"]["batting"]["strikeOuts"])
                    batting_log["IBB"] = int(player["stats"]["batting"]["intentionalWalks"])
                    batting_log["HBP"] = int(player["stats"]["batting"]["hitByPitch"])
                    batting_log["SH"] = int(player["stats"]["batting"]["sacBunts"])
                    batting_log["SF"] = int(player["stats"]["batting"]["sacFlies"])
                    batting_log["GIDP"] = int(player["stats"]["batting"]["groundIntoDoublePlay"])

                    batting_logs.append(batting_log)

                if player["stats"]["pitching"]:
                    pitching_log = {}
                    pitching_log["game_date"] = game["date"]
                    pitching_log["game_id"] = int(game["game_id"])
                    pitching_log["game_type"] = game["game_type"]
                    pitching_log["venue_id"] = int(game["venue_id"])
                    pitching_log["league_id"] = int(game["league_id"])
                    pitching_log["player_id"] = int(player["person"]["id"])
                    pitching_log["W"] = int(player["stats"]["pitching"].get("wins", ""))
                    pitching_log["L"] = int(player["stats"]["pitching"].get("losses", ""))
                    pitching_log["G"] = int(player["stats"]["pitching"].get("gamesPlayed", ""))
                    pitching_log["GS"] = int(player["stats"]["pitching"].get("gamesStarted", ""))
                    pitching_log["CG"] = int(player["stats"]["pitching"].get("completeGames", ""))
                    pitching_log["SHO"] = int(player["stats"]["pitching"].get("shutouts", ""))
                    pitching_log["SV"] = int(player["stats"]["pitching"].get("saves", ""))
                    pitching_log["HLD"] = int(player["stats"]["pitching"].get("holds", ""))
                    pitching_log["BFP"] = int(player["stats"]["pitching"].get("battersFaced", ""))
                    pitching_log["IP"] = float(player["stats"]["pitching"].get("inningsPitched", ""))
                    pitching_log["H"] = int(player["stats"]["pitching"].get("hits", ""))
                    pitching_log["ER"] = int(player["stats"]["pitching"].get("earnedRuns", ""))
                    pitching_log["R"] = int(player["stats"]["pitching"].get("runs", ""))
                    pitching_log["HR"] = int(player["stats"]["pitching"].get("homeRuns", ""))
                    pitching_log["SO"] = int(player["stats"]["pitching"].get("strikeOuts", ""))
                    pitching_log["BB"] = int(player["stats"]["pitching"].get("baseOnBalls", ""))
                    pitching_log["IBB"] = int(player["stats"]["pitching"].get("intentionalWalks", ""))
                    pitching_log["HBP"] = int(player["stats"]["pitching"].get("hitByPitch", ""))
                    pitching_log["WP"] = int(player["stats"]["pitching"].get("wildPitches", ""))
                    pitching_log["BK"] = int(player["stats"]["pitching"].get("balks", ""))

                    if pitching_log["GS"] > 0 and pitching_log["IP"] >= 6 and pitching_log["ER"] <= 3:
                        pitching_log["QS"] = 1
                    else:
                        pitching_log["QS"] = 0

                    pitching_logs.append(pitching_log)

    return batting_logs, pitching_logs


if __name__ == "__main__":
    main()