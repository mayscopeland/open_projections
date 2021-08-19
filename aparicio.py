import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path


def main():

    # project(545361, "2021-04-01")

    project_all("2021-07-17")


def project_all(projection_date_str):
    project(projection_date_str, BATTING, True)
    project(projection_date_str, PITCHING, False)


def project(projection_date_str, settings, is_batting):

    MAX_DAYS_AGO = 2000
    LG_AVG_PCT = 0.15
    PROJECTED_PA = 650
    PROJECTED_BF = 800
    MIN_RP_BF = 250

    # Compared to the max appearances, what percentage does a player need to get a projection?
    APPEARANCE_THRESHOLD = 0.10

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

    pr = df.groupby(["player_id"]).sum()
    pr = pr[settings["stat_cols"]]

    if is_batting:
        appearances = "PA"
        pr[appearances] = pr["AB"] + pr["BB"] + pr["HBP"] + pr["SH"] + pr["SF"]
    else:
        appearances = "BFP"
        pr["start_pct"] = pr["GS"] / pr["G"]

    # Our regression to the mean will be 15% of the top player's PA
    max_pa = pr[appearances].max()
    regression_pa = LG_AVG_PCT * max_pa

    # Clear out players with too few appearances (long-retired, pitchers batting, etc.)
    pr = pr[pr[appearances] > (max_pa * APPEARANCE_THRESHOLD)]

    # This should only be league average of MLB players
    lg_avg = pr.mean()
    factor = regression_pa / lg_avg[appearances]
    lg_avg = lg_avg * factor

    lg_avg["start_pct"] = 0
    pr = pr + lg_avg

    # Scale everyone to the same PA
    if is_batting:
        pr["projected_pa"] = PROJECTED_PA
    else:
        pr["projected_pa"] = MIN_RP_BF + pr["start_pct"] * (PROJECTED_BF - MIN_RP_BF)

    pr = pr.multiply(pr["projected_pa"] / pr[appearances], axis="index")

    # Clean up calc columns
    pr = pr.drop("projected_pa", 1)
    pr = pr.drop("start_pct", 1)

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
    df.round().to_csv(filepath / (date + ".csv"), index_label="player_id")

def load_projection(date, is_batting):

    if is_batting:
        filepath = Path(__file__).parent / "projections" / "batting"
    else:
        filepath = Path(__file__).parent / "projections" / "pitching"
    
    return pd.read_csv(filepath / (date + ".csv"))


def load_player_projections(player_id, is_batting):

    player = pd.DataFrame()

    if is_batting:
        filedir = Path(__file__).parent / "projections" / "batting"
    else:
        filedir = Path(__file__).parent / "projections" / "pitching"

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
        player.sort_values(by=["Date"], inplace=True, ascending=False)

        # Only keep the most recent projection 
        # and 1 projection for each of the previous months.
        player = player[(player["Date"] == player["Date"].max()) | (pd.DatetimeIndex(player["Date"]).day == 1)]


    return player 

def search_players(search_string):

    return True


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
        "AB": 1.00,
        "R": 0.79,
        "H": 0.95,
        "2B": 0.80,
        "3B": 0.84,
        "HR": 0.66,
        "RBI": 0.79,
        "SB": 0.72,
        "CS": 1.01,
        "BB": 0.78,
        "SO": 0.90,
        "IBB": 0.78,
        "HBP": 0.78,
        "SH": 0.78,
        "SF": 0.78,
        "GIDP": 0.78,
    },
    "aa_factors": {
        "AB": 1.02,
        "R": 0.82,
        "H": 0.99,
        "2B": 0.85,
        "3B": 0.95,
        "HR": 0.67,
        "RBI": 0.83,
        "SB": 0.70,
        "CS": 0.91,
        "BB": 0.79,
        "SO": 0.90,
        "IBB": 0.79,
        "HBP": 0.79,
        "SH": 0.79,
        "SF": 0.79,
        "GIDP": 0.79,
    },
    "high_a_factors": {
        "AB": 1.03,
        "R": 0.78,
        "H": 0.95,
        "2B": 0.79,
        "3B": 0.81,
        "HR": 0.61,
        "RBI": 0.75,
        "SB": 0.51,
        "CS": 0.93,
        "BB": 0.72,
        "SO": 0.93,
        "IBB": 0.72,
        "HBP": 0.72,
        "SH": 0.72,
        "SF": 0.72,
        "GIDP": 0.72,
    },
    "low_a_factors": {
        "AB": 1.05,
        "R": 0.69,
        "H": 0.92,
        "2B": 0.76,
        "3B": 0.69,
        "HR": 0.65,
        "RBI": 0.68,
        "SB": 0.46,
        "CS": 0.84,
        "BB": 0.64,
        "SO": 0.89,
        "IBB": 0.64,
        "HBP": 0.64,
        "SH": 0.64,
        "SF": 0.64,
        "GIDP": 0.64,
    },
    "rookie_factors": {
        "AB": 1.08,
        "R": 0.51,
        "H": 0.77,
        "2B": 0.63,
        "3B": 0.26,
        "HR": 0.39,
        "RBI": 0.48,
        "SB": 0.27,
        "CS": 0.48,
        "BB": 0.54,
        "SO": 1.06,
        "IBB": 0.54,
        "HBP": 0.54,
        "SH": 0.54,
        "SF": 0.54,
        "GIDP": 0.54,
    },
    "fall_factors": {
        "AB": 1.02,
        "R": 0.82,
        "H": 0.99,
        "2B": 0.85,
        "3B": 0.95,
        "HR": 0.67,
        "RBI": 0.83,
        "SB": 0.70,
        "CS": 0.91,
        "BB": 0.79,
        "SO": 0.90,
        "IBB": 0.79,
        "HBP": 0.79,
        "SH": 0.79,
        "SF": 0.79,
        "GIDP": 0.79,
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
        "W": 0.92,
        "L": 1.14,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.96,
        "HLD": 0.96,
        "BFP": 1.00,
        "IP": 1.00,
        "H": 1.13,
        "ER": 0.92,
        "R": 0.92,
        "HR": 0.88,
        "SO": 0.56,
        "BB": 0.87,
        "IBB": 0.87,
        "HBP": 0.87,
        "WP": 0.87,
        "BK": 0.87,
    },
    "aa_factors": {
        "W": 0.92,
        "L": 1.24,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.99,
        "HLD": 0.99,
        "BFP": 0.99,
        "IP": 0.99,
        "H": 1.25,
        "ER": 1.05,
        "R": 1.05,
        "HR": 1.02,
        "SO": 0.50,
        "BB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
    "high_a_factors": {
        "W": 0.92,
        "L": 1.31,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.96,
        "HLD": 0.96,
        "BFP": 0.98,
        "IP": 0.98,
        "H": 1.28,
        "ER": 1.03,
        "R": 1.03,
        "HR": 1.28,
        "SO": 0.46,
        "BB": 0.92,
        "IBB": 0.92,
        "HBP": 0.92,
        "WP": 0.92,
        "BK": 0.92,
    },
    "low_a_factors": {
        "W": 0.86,
        "L": 1.27,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 1.04,
        "HLD": 1.04,
        "BFP": 1.00,
        "IP": 1.00,
        "H": 1.30,
        "ER": 1.04,
        "R": 1.04,
        "HR": 1.57,
        "SO": 0.45,
        "BB": 0.89,
        "IBB": 0.89,
        "HBP": 0.89,
        "WP": 0.89,
        "BK": 0.89,
    },
    "rookie_factors": {
        "W": 0.68,
        "L": 1.10,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 1.04,
        "HLD": 1.04,
        "BFP": 0.96,
        "IP": 0.96,
        "H": 1.30,
        "ER": 1.08,
        "R": 1.08,
        "HR": 2.01,
        "SO": 0.38,
        "BB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
    "fall_factors": {
        "W": 0.92,
        "L": 1.24,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.99,
        "HLD": 0.99,
        "BFP": 0.99,
        "IP": 0.99,
        "H": 1.25,
        "ER": 1.05,
        "R": 1.05,
        "HR": 1.02,
        "SO": 0.50,
        "BB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
}


if __name__ == "__main__":
    main()
