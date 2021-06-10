import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path


def main():

    # project(545361, "2021-04-01")

    project_all("2021-05-10")


def project_all(projection_date_str):
    project(projection_date_str, BATTING, True)
    project(projection_date_str, PITCHING, False)


def project(projection_date_str, settings, is_batting):

    MAX_DAYS_AGO = 2000
    LG_AVG_PCT = 0.15
    PROJECTED_PA = 650

    # MLB's "GameTypes"
    SPRING_TRAINING = "S"
    EXHIBITION = "E"
    # REGULAR_SEASON = "R"
    # POST_SEASON = "P"

    # MLB's "SportIDs" for various leagues
    AAA = 11
    AA = 12
    HIGH_A = 13
    LOW_A = 14
    ROOKIE = 16
    FALL = 17

    # Load all player stats
    df = load_gamelogs(is_batting)

    # Calculate days ago
    projection_date = datetime.strptime(projection_date_str, "%Y-%m-%d")
    df["date"] = pd.to_datetime(df["date"], infer_datetime_format=True)

    df["days_ago"] = (projection_date - df["date"]).dt.days

    # Remove data before and after the projection window
    df = df[df["days_ago"] <= MAX_DAYS_AGO]
    df = df[df["days_ago"] > 0]

    # Weight stats by decay rate
    for stat in settings["stat_cols"]:
        df[stat] = df[stat] * (settings["decay_rates"][stat] ** df["days_ago"])

        # Reduce spring training and exhibition games
        df[stat] = np.where(
            df["game_type"] == SPRING_TRAINING, df[stat] * 0.45, df[stat]
        )
        df[stat] = np.where(df["game_type"] == EXHIBITION, df[stat] * 0.45, df[stat])

        # Reduce minor league stats
        df[stat] = np.where(
            df["league_id"] == AAA, df[stat] * settings["aaa_factors"][stat], df[stat]
        )
        df[stat] = np.where(
            df["league_id"] == AA, df[stat] * settings["aa_factors"][stat], df[stat]
        )
        df[stat] = np.where(
            df["league_id"] == HIGH_A,
            df[stat] * settings["high_a_factors"][stat],
            df[stat],
        )
        df[stat] = np.where(
            df["league_id"] == LOW_A,
            df[stat] * settings["low_a_factors"][stat],
            df[stat],
        )
        df[stat] = np.where(
            df["league_id"] == ROOKIE,
            df[stat] * settings["rookie_factors"][stat],
            df[stat],
        )
        df[stat] = np.where(
            df["league_id"] == FALL, df[stat] * settings["fall_factors"][stat], df[stat]
        )


    # Group stats by player
    # Replace by pandas groupby?
    player_ids = df["player_id"].unique()
    pr = pd.DataFrame()
    for player_id in player_ids:
        player_games = df.loc[df["player_id"] == player_id].copy()
        projection = player_games[settings["stat_cols"]].sum()
        projection = projection.rename(player_id)
        pr = pr.append(projection)

    if is_batting:
        appearances = "PA"
        pr[appearances] = pr["AB"] + pr["BB"] + pr["HBP"] + pr["SH"] + pr["SF"]
    else:
        appearances = "BFP"

    # Our regression to the mean will be 15% of the top player's PA
    max_pa = pr[appearances].max()
    regression_pa = LG_AVG_PCT * max_pa

    # Clear out players with too few appearances (long-retired, pitchers batting, etc.)
    pr = pr[pr[appearances] > (max_pa * 0.1)]

    # This should only be league average of MLB players
    lg_avg = pr.mean()
    factor = regression_pa / lg_avg[appearances]
    lg_avg = lg_avg * factor

    pr = pr + lg_avg

    # Scale everyone to the same PA
    pr = pr.multiply(PROJECTED_PA / pr[appearances], axis="index")

    # Add names to the data for easy readability
    pr = pr.join(load_names(), how="left")

    print(pr.head())
    save_projection(projection_date_str, pr, is_batting)

def load_gamelogs(is_batting):
    df = pd.DataFrame()

    filepath = Path(__file__).parent
    if is_batting:
        df = pd.read_csv(filepath / "stats" / "batting.csv")
    else:
        df = pd.read_csv(filepath / "stats" / "pitching.csv")

        df["IP"] = df["IP"].map(convert_ip)

    return df

# Convert IP fractional notation (.1 .2) to true decimals (.33 .67)
def convert_ip(ip):
    return int(ip) + (ip % 1 * 10 / 3)


def load_names():

    names = pd.DataFrame()
    names = pd.read_csv("https://raw.githubusercontent.com/chadwickbureau/register/master/data/people.csv", low_memory=False)

    names = names[["key_mlbam", "name_last", "name_first"]]
    names.set_index("key_mlbam", inplace=True)

    return names


def save_projection(date, df, is_batting):

    if is_batting:
        filepath = Path(__file__).parent / "projections" / "batting"
    else:
        filepath = Path(__file__).parent / "projections" / "pitching"
    df.round().to_csv(filepath / (date + ".csv"))


def load_player_projections(player_id, is_batting):

    player = pd.DataFrame()

    if is_batting:
        filedir = Path(__file__).parent / "projections" / "batting"
    else:
        filedir = Path(__file__).parent / "projections" / "batting"

    files = [x for x in filedir.iterdir() if x.is_file()]
    for file in files:
        df = pd.read_csv(file, index_col=0)
        df["Date"] = file.stem

        if player_id in df.index:
            player = player.append(df.loc[[player_id]])
    
    if not player.empty:

        if is_batting:
            int_cols = ["PA","AB","H","2B","3B","HR","R","RBI","SB","CS","BB","SO","GIDP","HBP","SH","SF","IBB"]
        else:
            int_cols = ["W","L","G","GS","CG","SHO","SV","HLD","IP","H","R","ER","HR","BB","IBB","SO","HBP","BK","WP","BFP"]
        player[int_cols] = player[int_cols].astype(int)
        player.sort_values(by=['Date'], inplace=True, ascending=False)

    return player 


BATTING = {
    "stat_cols": [
        "AB",
        "R",
        "H",
        "2B",
        "3B",
        "HR",
        "RBI",
        "SB",
        "CS",
        "BB",
        "SO",
        "IBB",
        "HBP",
        "SH",
        "SF",
        "GIDP",
    ],
    "decay_rates": {
        "AB": 0.9994,
        "R": 0.9994,
        "H": 0.9994,
        "2B": 0.9994,
        "3B": 0.9994,
        "HR": 0.9994,
        "RBI": 0.9994,
        "SB": 0.9994,
        "CS": 0.9994,
        "BB": 0.9994,
        "SO": 0.9994,
        "IBB": 0.9994,
        "HBP": 0.9994,
        "SH": 0.9994,
        "SF": 0.9994,
        "GIDP": 0.9994,
    },
    "aaa_factors": {
        "AB": 1.01,
        "R": 0.86,
        "H": 0.91,
        "2B": 0.90,
        "3B": 0.76,
        "HR": 0.86,
        "RBI": 0.85,
        "SB": 0.85,
        "CS": 1.00,
        "BB": 0.89,
        "SO": 0.94,
        "IBB": 0.89,
        "HBP": 0.89,
        "SH": 0.89,
        "SF": 0.89,
        "GIDP": 0.89,
    },
    "aa_factors": {
        "AB": 1.01,
        "R": 0.89,
        "H": 0.90,
        "2B": 0.95,
        "3B": 0.95,
        "HR": 0.82,
        "RBI": 0.86,
        "SB": 0.84,
        "CS": 0.97,
        "BB": 0.89,
        "SO": 0.99,
        "IBB": 0.89,
        "HBP": 0.89,
        "SH": 0.89,
        "SF": 0.89,
        "GIDP": 0.89,
    },
    "high_a_factors": {
        "AB": 1.02,
        "R": 0.90,
        "H": 0.89,
        "2B": 0.97,
        "3B": 0.82,
        "HR": 1.03,
        "RBI": 0.88,
        "SB": 0.85,
        "CS": 0.89,
        "BB": 0.86,
        "SO": 1.02,
        "IBB": 0.86,
        "HBP": 0.86,
        "SH": 0.86,
        "SF": 0.86,
        "GIDP": 0.86,
    },
    "low_a_factors": {
        "AB": 1.04,
        "R": 0.81,
        "H": 0.83,
        "2B": 0.85,
        "3B": 0.79,
        "HR": 1.03,
        "RBI": 0.78,
        "SB": 0.71,
        "CS": 0.92,
        "BB": 0.74,
        "SO": 1.13,
        "IBB": 0.74,
        "HBP": 0.74,
        "SH": 0.74,
        "SF": 0.74,
        "GIDP": 0.74,
    },
    "rookie_factors": {
        "AB": 1.06,
        "R": 0.60,
        "H": 0.73,
        "2B": 0.82,
        "3B": 0.59,
        "HR": 0.55,
        "RBI": 0.59,
        "SB": 0.61,
        "CS": 0.82,
        "BB": 0.62,
        "SO": 1.21,
        "IBB": 0.62,
        "HBP": 0.62,
        "SH": 0.62,
        "SF": 0.62,
        "GIDP": 0.62,
    },
    "fall_factors": {
        "AB": 1.04,
        "R": 0.85,
        "H": 0.95,
        "2B": 1.09,
        "3B": 0.77,
        "HR": 1.06,
        "RBI": 0.78,
        "SB": 0.74,
        "CS": 1.00,
        "BB": 0.66,
        "SO": 0.93,
        "IBB": 0.66,
        "HBP": 0.66,
        "SH": 0.66,
        "SF": 0.66,
        "GIDP": 0.66,
    },
}

PITCHING = {
    "stat_cols": [
        "W",
        "L",
        "G",
        "GS",
        "CG",
        "SHO",
        "SV",
        "HLD",
        "BFP",
        "IP",
        "H",
        "ER",
        "R",
        "HR",
        "SO",
        "BB",
        "IBB",
        "HBP",
        "WP",
        "BK",
    ],
    "decay_rates": {
        "W": 0.999,
        "L": 0.999,
        "G": 0.999,
        "GS": 0.999,
        "CG": 0.999,
        "SHO": 0.999,
        "SV": 0.999,
        "HLD": 0.999,
        "BFP": 0.999,
        "IP": 0.999,
        "H": 0.999,
        "ER": 0.999,
        "R": 0.999,
        "HR": 0.999,
        "SO": 0.999,
        "BB": 0.999,
        "IBB": 0.999,
        "HBP": 0.999,
        "WP": 0.999,
        "BK": 0.999,
    },
    "aaa_factors": {
        "W": 0.99,
        "L": 1.44,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.89,
        "HLD": 0.89,
        "BFP": 1.00,
        "IP": 1.00,
        "H": 1.11,
        "ER": 1.15,
        "R": 1.15,
        "HR": 1.37,
        "SO": 0.59,
        "BB": 1.03,
        "IBB": 1.03,
        "HBP": 1.03,
        "WP": 1.03,
        "BK": 1.03,
    },
    "aa_factors": {
        "W": 0.89,
        "L": 1.32,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.94,
        "HLD": 0.94,
        "BFP": 0.98,
        "IP": 0.98,
        "H": 1.14,
        "ER": 1.26,
        "R": 1.26,
        "HR": 1.48,
        "SO": 0.58,
        "BB": 1.08,
        "IBB": 1.08,
        "HBP": 1.08,
        "WP": 1.08,
        "BK": 1.08,
    },
    "high_a_factors": {
        "W": 0.89,
        "L": 1.44,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.92,
        "HLD": 0.92,
        "BFP": 0.97,
        "IP": 0.97,
        "H": 1.19,
        "ER": 1.37,
        "R": 1.37,
        "HR": 2.20,
        "SO": 0.56,
        "BB": 1.11,
        "IBB": 1.11,
        "HBP": 1.11,
        "WP": 1.11,
        "BK": 1.11,
    },
    "low_a_factors": {
        "W": 0.75,
        "L": 1.26,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.91,
        "HLD": 0.91,
        "BFP": 0.94,
        "IP": 0.94,
        "H": 1.30,
        "ER": 1.59,
        "R": 1.59,
        "HR": 3.13,
        "SO": 0.44,
        "BB": 1.11,
        "IBB": 1.11,
        "HBP": 1.11,
        "WP": 1.11,
        "BK": 1.11,
    },
    "rookie_factors": {
        "W": 0.74,
        "L": 1.34,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.94,
        "HLD": 0.94,
        "BFP": 0.99,
        "IP": 0.99,
        "H": 1.26,
        "ER": 1.33,
        "R": 1.33,
        "HR": 1.98,
        "SO": 0.45,
        "BB": 0.98,
        "IBB": 0.98,
        "HBP": 0.98,
        "WP": 0.98,
        "BK": 0.98,
    },
    "fall_factors": {
        "W": 0.61,
        "L": 0.87,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.00,
        "HLD": 0.00,
        "BFP": 1.00,
        "IP": 1.00,
        "H": 1.25,
        "ER": 1.25,
        "R": 1.25,
        "HR": 2.03,
        "SO": 0.55,
        "BB": 0.81,
        "IBB": 0.81,
        "HBP": 0.81,
        "WP": 0.81,
        "BK": 0.81,
    },
}


if __name__ == "__main__":
    main()
