@@ -0,0 +1,217 @@
import pandas as pd
import requests
import os
import datetime
import calendar
import glob


def main():
    build_monthly_gamelogs("2021", "03")
    combine_gamelogs()
    #build_gamelogs("2021")
    #combine_player_logs(670623)

def combine_player_logs(player_id):
    filepath = os.path.dirname(__file__)
    all_batting = glob.glob(filepath + "\\data\\batting\\*.csv")

    li = []

    for filename in all_batting:
        df = pd.read_csv(filename, index_col=None, header=0)
        li.append(df)

    frame = pd.concat(li, axis=0, ignore_index=True)

    player = frame[frame["player_id"] == player_id]
    print(player.head(20))
    player.to_csv(os.path.dirname(__file__) + "\\data\\player.csv")


def combine_gamelogs():
    filepath = os.path.dirname(__file__)
    all_batting = glob.glob(filepath + "\\data\\batting\\*.csv")

    li = []

    for filename in all_batting:
        df = pd.read_csv(filename, index_col=None, header=0)
        li.append(df)

    frame = pd.concat(li, axis=0, ignore_index=True)
    
    frame.to_csv(os.path.dirname(__file__) + "\\data\\all_batting.csv", index=False)

    all_pitching = glob.glob(filepath + "\\data\\pitching\\*.csv")

    li = []

    for filename in all_pitching:
        df = pd.read_csv(filename, index_col=None, header=0)
        li.append(df)

    frame = pd.concat(li, axis=0, ignore_index=True)
    frame["QS"] = frame.apply(quality_start, axis=1)
    
    frame.to_csv(os.path.dirname(__file__) + "\\data\\all_pitching.csv", index=False)


def quality_start(s):
    if s["GS"] > 0:
        if s["IP"] >= 6:
            if s["ER"] <= 3:
                return 1
    
    return 0


def build_gamelogs(year):

    bb_months = ["01","02","03","04","05","06","07","08","09","10","11","12"]

    for month in bb_months:
        build_monthly_gamelogs(year, month)


def build_monthly_gamelogs(year, month):

    # Get a list of days in the month
    num_days = calendar.monthrange(int(year), int(month))[1]
    game_dates = [datetime.date(int(year), int(month), day) for day in range(1, num_days + 1)]

    for game_date in game_dates:
        build_daily_gamelogs(game_date.strftime("%Y-%m-%d"))


def build_daily_gamelogs(date_string):

    df_batting = pd.DataFrame()
    df_pitching = pd.DataFrame()
    games = []
    filename = date_string + ".csv"
        
    if not os.path.exists(os.path.dirname(__file__) + "\\data\\batting\\" + filename):
        print(date_string)
        # Get a list of game ids for games on this date
        games = get_games(date_string)

    # For each game, get the stats for every player
    for game in games:
        game_batting, game_pitching = get_game_logs(game)

        # Convert our list to a DataFrame
        df_game_batting = pd.DataFrame(game_batting)
        df_game_pitching = pd.DataFrame(game_pitching)

        # Append daily stats to our running total
        df_batting = df_batting.append(df_game_batting)
        df_pitching = df_pitching.append(df_game_pitching)
        #print(df_game_batting.head())
        #print(df_game_pitching.head())

    if games:
        df_batting.to_csv(os.path.dirname(__file__) + "\\data\\batting\\" + filename, index=False)
        df_pitching.to_csv(os.path.dirname(__file__) + "\\data\\pitching\\" + filename, index=False)

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

    for team in game_info["teams"].values():
        for player in team["players"].values():
            if player["stats"]["batting"]:
                batting_log = {}
                batting_log["date"] = game["date"]
                batting_log["game_id"] = game["game_id"]
                batting_log["game_type"] = game["game_type"]
                batting_log["venue_id"] = game["venue_id"]
                batting_log["league_id"] = game["league_id"]
                batting_log["player_id"] = player["person"]["id"]
                batting_log["batting_order"] = player.get("battingOrder", "")
                batting_log["AB"] = player["stats"]["batting"]["atBats"]
                batting_log["R"] = player["stats"]["batting"]["runs"]
                batting_log["H"] = player["stats"]["batting"]["hits"]
                batting_log["2B"] = player["stats"]["batting"]["doubles"]
                batting_log["3B"] = player["stats"]["batting"]["triples"]
                batting_log["HR"] = player["stats"]["batting"]["homeRuns"]
                batting_log["RBI"] = player["stats"]["batting"]["rbi"]
                batting_log["SB"] = player["stats"]["batting"]["stolenBases"]
                batting_log["CS"] = player["stats"]["batting"]["caughtStealing"]
                batting_log["BB"] = player["stats"]["batting"]["baseOnBalls"]
                batting_log["SO"] = player["stats"]["batting"]["strikeOuts"]
                batting_log["IBB"] = player["stats"]["batting"]["intentionalWalks"]
                batting_log["HBP"] = player["stats"]["batting"]["hitByPitch"]
                batting_log["SH"] = player["stats"]["batting"]["sacBunts"]
                batting_log["SF"] = player["stats"]["batting"]["sacFlies"]
                batting_log["GIDP"] = player["stats"]["batting"]["groundIntoDoublePlay"]

                batting_logs.append(batting_log)

            if player["stats"]["pitching"]:
                pitching_log = {}
                pitching_log["date"] = game["date"]
                pitching_log["game_id"] = game["game_id"]
                pitching_log["game_type"] = game["game_type"]
                pitching_log["venue_id"] = game["venue_id"]
                pitching_log["league_id"] = game["league_id"]
                pitching_log["player_id"] = player["person"]["id"]
                pitching_log["W"] = player["stats"]["pitching"].get("wins", "")
                pitching_log["L"] = player["stats"]["pitching"].get("losses", "")
                pitching_log["G"] = player["stats"]["pitching"].get("gamesPlayed", "")
                pitching_log["GS"] = player["stats"]["pitching"].get("gamesStarted", "")
                pitching_log["CG"] = player["stats"]["pitching"].get("completeGames", "")
                pitching_log["SHO"] = player["stats"]["pitching"].get("shutouts", "")
                pitching_log["SV"] = player["stats"]["pitching"].get("saves", "")
                pitching_log["HLD"] = player["stats"]["pitching"].get("holds", "")
                pitching_log["BFP"] = player["stats"]["pitching"].get("battersFaced", "")
                pitching_log["IP"] = player["stats"]["pitching"].get("inningsPitched", "")
                pitching_log["H"] = player["stats"]["pitching"].get("hits", "")
                pitching_log["ER"] = player["stats"]["pitching"].get("earnedRuns", "")
                pitching_log["R"] = player["stats"]["pitching"].get("runs", "")
                pitching_log["HR"] = player["stats"]["pitching"].get("homeRuns", "")
                pitching_log["SO"] = player["stats"]["pitching"].get("strikeOuts", "")
                pitching_log["BB"] = player["stats"]["pitching"].get("baseOnBalls", "")
                pitching_log["IBB"] = player["stats"]["pitching"].get("intentionalWalks", "")
                pitching_log["HBP"] = player["stats"]["pitching"].get("hitByPitch", "")
                pitching_log["WP"] = player["stats"]["pitching"].get("wildPitches", "")
                pitching_log["BK"] = player["stats"]["pitching"].get("balks", "")

                pitching_logs.append(pitching_log)

    return batting_logs, pitching_logs


if __name__ == "__main__":
    main()