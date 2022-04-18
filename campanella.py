import pandas as pd
from datetime import datetime
from pathlib import Path
import sqlite3

def main():
    project_all("2022-04-01")


def project_all(projection_date_str):
    project(projection_date_str, BATTING, True)
    project(projection_date_str, PITCHING, False)


def project(projection_date_str, settings, is_batting):

    MAX_DAYS_AGO = 2000
    TOP_PA = 725
    MIN_PA = 400

    TOP_BF_SP = 850
    MIN_BF_SP = 500
    TOP_BF_RP = 330
    MIN_BF_RP = 200

    # Compared to the max appearances, what percentage does a player need to get a projection?
    APPEARANCE_THRESHOLD = 0.11

    # MLB's "GameTypes"
    SPRING_TRAINING = "S"
    EXHIBITION = "E"
    REGULAR_SEASON = "R"
    # POST_SEASON = "P"

    # MLB's "SportIDs" for various leagues
    MLB = 1
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
    df["game_date"] = pd.to_datetime(df["game_date"], infer_datetime_format=True)

    df["days_ago"] = (projection_date - df["game_date"]).dt.days

    # Remove data before and after the projection window
    df = df[df["days_ago"] <= MAX_DAYS_AGO]
    df = df[df["days_ago"] > 0]

    # Setup some initially calculated columns
    df["UIBB"] = df["BB"] - df["IBB"]
    if is_batting:
        df["1B"] = df["H"] - df["HR"] - df["3B"] - df["2B"]
        df["PA"] = df["AB"] + df["BB"] + df["HBP"] + df["SH"] + df["SF"]
        appearances = "PA"
    else:
        appearances = "BFP"

    # Calculate league average before applying weights
    lg_avg = df[df["league_id"] == MLB]
    lg_avg = lg_avg[lg_avg["game_type"] == REGULAR_SEASON]
    if is_batting:
        lg_avg = lg_avg.groupby(["player_id"]).sum()
        max_pa = lg_avg[appearances].max()
        lg_avg = lg_avg[lg_avg[appearances] > (max_pa * APPEARANCE_THRESHOLD)]
        lg_avg = lg_avg.mean()
    else:
        lg_avg_sp = lg_avg[lg_avg["GS"] == 1]
        lg_avg_sp = lg_avg_sp.groupby(["player_id"]).sum()
        max_pa = lg_avg_sp[appearances].max()
        lg_avg_sp = lg_avg_sp[lg_avg_sp[appearances] > (max_pa * APPEARANCE_THRESHOLD)]
        lg_avg_sp = lg_avg_sp.mean()

        lg_avg_rp = lg_avg[lg_avg["GS"] == 0]
        lg_avg_rp = lg_avg_rp.groupby(["player_id"]).sum()
        max_pa = lg_avg_rp[appearances].max()
        lg_avg_rp = lg_avg_rp[lg_avg_rp[appearances] > (max_pa * APPEARANCE_THRESHOLD)]
        lg_avg_rp = lg_avg_rp.mean()


    # Weight stats by decay rate
    for stat in settings["base_stats"]:
        df[stat + "_denom"] = df[appearances]
        df[stat] *= (settings["decay_rates"][stat] ** df["days_ago"]) 
        df[stat + "_denom"] *= (settings["decay_rates"][stat] ** df["days_ago"])

        # Reduce spring training and exhibition games
        df.loc[df["game_type"] == SPRING_TRAINING, stat] *= 0.45
        df.loc[df["game_type"] == SPRING_TRAINING, stat + "_denom"] *= 0.45
        df.loc[df["game_type"] == EXHIBITION, stat] *= 0.45
        df.loc[df["game_type"] == EXHIBITION, stat + "_denom"] *= 0.45

        # Reduce minor league stats
        df.loc[df["league_id"] == AAA, stat] *= settings["aaa_factors"][stat]
        df.loc[df["league_id"] == AA, stat] *= settings["aa_factors"][stat]
        df.loc[df["league_id"] == HIGH_A, stat] *= settings["high_a_factors"][stat]
        df.loc[df["league_id"] == LOW_A, stat] *= settings["low_a_factors"][stat]
        df.loc[df["league_id"] == ROOKIE, stat] *= settings["rookie_factors"][stat]
        df.loc[df["league_id"] == FALL, stat] *= settings["fall_factors"][stat]

    # For projected PA/BF, we're only considering MLB regular season
    df[appearances] *= (settings["decay_rates"][appearances] ** df["days_ago"])
    df["proj_app"] = df[appearances]
    df.loc[df["game_type"] != REGULAR_SEASON, "proj_app"] *= 0
    df.loc[df["league_id"] != MLB, "proj_app"] *= 0

    # Combine a player's daily data into a single row
    pr = df.groupby(["player_id"]).sum()

    # Cull out players that don't have enough playing time
    max_pa = pr[appearances].max()
    pr = pr[pr[appearances] > (max_pa * APPEARANCE_THRESHOLD)]

    if not is_batting:
        pr["start_pct"] = (pr["GS"] * 5) / ((pr["GS"] * 5) + (pr["G"] - pr["GS"]))

    # Add league average
    for stat in settings["base_stats"]:
        
        if is_batting:
            pr[stat] += (lg_avg[stat] / lg_avg[appearances]) * settings["regression_pa"][stat]
            pr[stat + "_denom"] += settings["regression_pa"][stat]
        else:
            pr[stat] += pr["start_pct"] * (lg_avg_sp[stat] / lg_avg_sp[appearances]) * settings["regression_pa"][stat]
            pr[stat] += (1 - pr["start_pct"]) * (lg_avg_rp[stat] / lg_avg_rp[appearances]) * settings["regression_pa"][stat]
            pr[stat + "_denom"] += settings["regression_pa"][stat]

    # Scale everyone's PA/BF in relation to the top player
    if is_batting:
        pa_factor = (TOP_PA - MIN_PA) / pr["proj_app"].max()
        pr[appearances] = pr["proj_app"] * pa_factor + MIN_PA
    else:
        pa_factor_sp = (TOP_BF_SP - MIN_BF_SP) / pr["proj_app"].max()
        pa_factor_rp = (TOP_BF_RP - MIN_BF_RP) / pr.loc[pr["start_pct"] == 0, "proj_app"].max()
        pr[appearances] = (pr["proj_app"] * pa_factor_sp + MIN_BF_SP) * pr["start_pct"] + (pr["proj_app"] * pa_factor_rp + MIN_BF_RP) * (1 - pr["start_pct"])

    # Apply projected rates out to the projected playing time
    for stat in settings["base_stats"]:
        pr[stat] = pr[stat] / pr[stat + "_denom"] * pr[appearances]

    # Recalculate traditional stats based on components
    pr["BB"] = pr["IBB"] + pr["UIBB"]
    if is_batting:
        pr["H"] = pr["HR"] + pr["3B"] + pr["2B"] + pr["1B"]
        pr["AB"] = pr["PA"] - pr["BB"] - pr["HBP"] - pr["SF"]
    else:
        pr["IP"] = (pr["BFP"] - pr["H"] - pr["BB"] - pr["HBP"]) / 3

    # Rework ER/R with kwERA
    if not is_batting:
        pr["kwERA"] = 5.40 - 12 * (pr["SO"] - pr["BB"]) / pr["BFP"]
        pr["kwER"] = pr["kwERA"] / 9 * pr["IP"]
        pr["ER"] = (pr["kwER"] + pr["ER"]) / 2
        pr["R"] = (pr["kwER"] + pr["R"]) / 2

    pr = pr[settings["display_cols"]]

    # Add names to the data for easy readability
    pr = pr.join(load_names(), how="left")

    save_projection(projection_date_str, pr, is_batting)

def load_gamelogs(is_batting):
    df = pd.DataFrame()
    filepath = Path(__file__).parent

    con = sqlite3.connect(filepath / "gamelogs.db")

    if is_batting:
        df = pd.read_sql_query("SELECT * FROM batting", con)
    else:
        df = pd.read_sql_query("SELECT * FROM pitching", con)

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
        filepath = Path(__file__).parent / "projections" / "v3" / "batting"
    else:
        filepath = Path(__file__).parent / "projections" / "v3" / "pitching"
    df.round().to_csv(filepath / (date + ".csv"), index_label="mlbam_id")

def load_projection(date, is_batting):

    if is_batting:
        filepath = Path(__file__).parent / "projections" / "v3" / "batting"
    else:
        filepath = Path(__file__).parent / "projections" / "v3" / "pitching"
    
    return pd.read_csv(filepath / (date + ".csv"))


def load_player_projections(player_id, is_batting):

    player = pd.DataFrame()

    if is_batting:
        filedir = Path(__file__).parent / "projections" / "v3" / "batting"
    else:
        filedir = Path(__file__).parent / "projections" / "v3" / "pitching"

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
            int_cols = ["W","L","QS","G","GS","CG","SHO","SV","HLD","IP","H","R","ER","HR","BB","IBB","SO","HBP","BK","WP","BFP"]
        player[int_cols] = player[int_cols].astype(int)
        player.sort_values(by=["Date"], inplace=True, ascending=False)

        # Only keep the most recent projection 
        # and 1 projection for each of the previous months.
        player = player[player["Date"] <= datetime.today().strftime('%Y-%m-%d')]
        player = player[(player["Date"] == player["Date"].max()) | (pd.DatetimeIndex(player["Date"]).day == 1)]


    return player 

BATTING = {
    "display_cols": [
        "PA",
        "AB",
        "R",
        "H",
        "2B",
        "3B",
        "HR",
        "RBI",
        "SB",
        "CS",
        "SO",
        "BB",
        "IBB",
        "HBP",
        "SH",
        "SF",
        "GIDP",
    ],
    "base_stats": [
        "R",
        "1B",
        "2B",
        "3B",
        "HR",
        "RBI",
        "SB",
        "CS",
        "SO",
        "UIBB",
        "IBB",
        "HBP",
        "SH",
        "SF",
        "GIDP",
    ],
    "decay_rates": {
        "PA": 0.9955,
        "R": 0.9994,
        "1B": 0.9994,
        "2B": 0.9994,
        "3B": 0.9994,
        "HR": 0.9985,
        "RBI": 0.9994,
        "SB": 0.9974,
        "CS": 0.9974,
        "BB": 0.9974,
        "SO": 0.9965,
        "UIBB": 0.9974,
        "IBB": 0.9974,
        "HBP": 0.9994,
        "SH": 0.9994,
        "SF": 0.9994,
        "GIDP": 0.9994,
    },
    "regression_pa": {
        "R": 281,
        "1B": 141,
        "2B": 354,
        "3B": 213,
        "HR": 175,
        "RBI": 214,
        "SB": 81,
        "CS": 81,
        "SO": 92,
        "UIBB": 117,
        "IBB": 117,
        "HBP": 120,
        "SH": 200,
        "SF": 200,
        "GIDP": 200,
    },
    "aaa_factors": {
        "R": 0.79,
        "1B": 0.95,
        "2B": 0.80,
        "3B": 0.84,
        "HR": 0.66,
        "RBI": 0.79,
        "SB": 0.72,
        "CS": 1.01,
        "SO": 0.90,
        "UIBB": 0.78,
        "IBB": 0.78,
        "HBP": 0.78,
        "SH": 0.78,
        "SF": 0.78,
        "GIDP": 0.78,
    },
    "aa_factors": {
        "R": 0.82,
        "1B": 0.99,
        "2B": 0.85,
        "3B": 0.95,
        "HR": 0.67,
        "RBI": 0.83,
        "SB": 0.70,
        "CS": 0.91,
        "SO": 0.80,
        "UIBB": 0.79,
        "IBB": 0.79,
        "HBP": 0.79,
        "SH": 0.79,
        "SF": 0.79,
        "GIDP": 0.79,
    },
    "high_a_factors": {
        "R": 0.78,
        "1B": 0.95,
        "2B": 0.79,
        "3B": 0.81,
        "HR": 0.61,
        "RBI": 0.75,
        "SB": 0.51,
        "CS": 0.93,
        "SO": 0.83,
        "UIBB": 0.72,
        "IBB": 0.72,
        "HBP": 0.72,
        "SH": 0.72,
        "SF": 0.72,
        "GIDP": 0.72,
    },
    "low_a_factors": {
        "R": 0.69,
        "1B": 0.92,
        "2B": 0.76,
        "3B": 0.69,
        "HR": 0.65,
        "RBI": 0.68,
        "SB": 0.46,
        "CS": 0.84,
        "SO": 0.89,
        "UIBB": 0.64,
        "IBB": 0.64,
        "HBP": 0.64,
        "SH": 0.64,
        "SF": 0.64,
        "GIDP": 0.64,
    },
    "rookie_factors": {
        "R": 0.51,
        "1B": 0.77,
        "2B": 0.63,
        "3B": 0.26,
        "HR": 0.39,
        "RBI": 0.48,
        "SB": 0.27,
        "CS": 0.48,
        "SO": 1.06,
        "UIBB": 0.54,
        "IBB": 0.54,
        "HBP": 0.54,
        "SH": 0.54,
        "SF": 0.54,
        "GIDP": 0.54,
    },
    "fall_factors": {
        "R": 0.82,
        "1B": 0.99,
        "2B": 0.85,
        "3B": 0.95,
        "HR": 0.67,
        "RBI": 0.83,
        "SB": 0.70,
        "CS": 0.91,
        "SO": 0.80,
        "UIBB": 0.79,
        "IBB": 0.79,
        "HBP": 0.79,
        "SH": 0.79,
        "SF": 0.79,
        "GIDP": 0.79,
    },
}

PITCHING = {
    "display_cols": [
        "W",
        "L",
        "QS",
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
    "base_stats": [
        "W",
        "L",
        "QS",
        "G",
        "GS",
        "CG",
        "SHO",
        "SV",
        "HLD",
        "H",
        "ER",
        "R",
        "HR",
        "SO",
        "UIBB",
        "IBB",
        "HBP",
        "WP",
        "BK",
    ],
    "decay_rates": {
        "BFP": 0.9955,
        "W": 0.998,
        "L": 0.999,
        "QS": 0.998,
        "G": 0.999,
        "GS": 0.999,
        "CG": 0.999,
        "SHO": 0.999,
        "SV": 0.997,
        "HLD": 0.997,
        "H": 0.998,
        "ER": 0.999,
        "R": 0.999,
        "HR": 0.998,
        "SO": 0.993,
        "UIBB": 0.998,
        "IBB": 1,
        "HBP": 0.9985,
        "WP": 0.999,
        "BK": 0.999,
    },
    "regression_pa": {
        "W": 200,
        "L": 200,
        "QS": 200,
        "G": 200,
        "GS": 200,
        "CG": 200,
        "SHO": 200,
        "SV": 100,
        "HLD": 100,
        "H": 200,
        "ER": 1200,
        "R": 1200,
        "HR": 1200,
        "SO": 70,
        "UIBB": 170,
        "IBB": 200,
        "HBP": 200,
        "WP": 200,
        "BK": 200,
    },
    "aaa_factors": {
        "W": 0.92,
        "L": 1.14,
        "QS": 0.92,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.96,
        "HLD": 0.96,
        "H": 1.13,
        "ER": 0.92,
        "R": 0.92,
        "HR": 0.88,
        "SO": 0.56,
        "UIBB": 0.87,
        "IBB": 0.87,
        "HBP": 0.87,
        "WP": 0.87,
        "BK": 0.87,
    },
    "aa_factors": {
        "W": 0.92,
        "L": 1.24,
        "QS": 0.92,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.99,
        "HLD": 0.99,
        "H": 1.25,
        "ER": 1.05,
        "R": 1.05,
        "HR": 1.02,
        "SO": 0.50,
        "UIBB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
    "high_a_factors": {
        "W": 0.92,
        "L": 1.31,
        "QS": 0.92,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.96,
        "HLD": 0.96,
        "H": 1.28,
        "ER": 1.03,
        "R": 1.03,
        "HR": 1.28,
        "SO": 0.46,
        "UIBB": 0.92,
        "IBB": 0.92,
        "HBP": 0.92,
        "WP": 0.92,
        "BK": 0.92,
    },
    "low_a_factors": {
        "W": 0.86,
        "L": 1.27,
        "QS": 0.86,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 1.04,
        "HLD": 1.04,
        "H": 1.30,
        "ER": 1.04,
        "R": 1.04,
        "HR": 1.57,
        "SO": 0.45,
        "UIBB": 0.89,
        "IBB": 0.89,
        "HBP": 0.89,
        "WP": 0.89,
        "BK": 0.89,
    },
    "rookie_factors": {
        "W": 0.68,
        "L": 1.10,
        "QS": 0.68,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 1.04,
        "HLD": 1.04,
        "H": 1.30,
        "ER": 1.08,
        "R": 1.08,
        "HR": 2.01,
        "SO": 0.38,
        "UIBB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
    "fall_factors": {
        "W": 0.92,
        "L": 1.24,
        "QS": 0.92,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.99,
        "HLD": 0.99,
        "H": 1.25,
        "ER": 1.05,
        "R": 1.05,
        "HR": 1.02,
        "SO": 0.50,
        "UIBB": 0.95,
        "IBB": 0.95,
        "HBP": 0.95,
        "WP": 0.95,
        "BK": 0.95,
    },
}


if __name__ == "__main__":
    main()
