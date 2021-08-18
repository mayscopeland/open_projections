import pandas as pd
from datetime import datetime
from pathlib import Path

def main():
    project_all("2021-04-01")


def project_all(projection_date_str):
    project(projection_date_str, BATTING, True)
    project(projection_date_str, PITCHING, False)


def project(projection_date_str, settings, is_batting):

    MAX_DAYS_AGO = 2000
    PROJECTED_PA = 650
    PROJECTED_BF = 800
    MIN_RP_BF = 250

    # Compared to the max appearances, what percentage does a player need to get a projection?
    APPEARANCE_THRESHOLD = 0.10

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
    df["date"] = pd.to_datetime(df["date"], infer_datetime_format=True)

    df["days_ago"] = (projection_date - df["date"]).dt.days

    # Remove data before and after the projection window
    df = df[df["days_ago"] <= MAX_DAYS_AGO]
    df = df[df["days_ago"] > 0]

    # Setup some initially calculated columns
    df["UIBB"] = df["BB"] - df["IBB"]
    if is_batting:
        appearances = "PA"
        df[appearances] = df["AB"] + df["BB"] + df["HBP"] + df["SH"] + df["SF"]
        df["1B"] = df["H"] - df["HR"] - df["3B"] - df["2B"]
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
        df[stat] = df[stat] * (settings["decay_rates"][stat] ** df["days_ago"]) 
        df[stat + "_denom"] = df[stat + "_denom"] * (settings["decay_rates"][stat] ** df["days_ago"])

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

    # Combine a player's daily data into a single row
    pr = df.groupby(["player_id"]).sum()

    if not is_batting:
        pr["start_pct"] = pr["GS"] / pr["G"]

    # Add league average
    for stat in settings["base_stats"]:
        
        if is_batting:
            pr[stat] += (lg_avg[stat] / lg_avg[appearances]) * settings["regression_pa"][stat]
            pr[stat + "_denom"] += settings["regression_pa"][stat]
        else:
            pr[stat] += pr["start_pct"] * (lg_avg_sp[stat] / lg_avg_sp[appearances]) * settings["regression_pa"][stat]
            pr[stat] += (1 - pr["start_pct"]) * (lg_avg_rp[stat] / lg_avg_rp[appearances]) * settings["regression_pa"][stat]
            #pr[stat] += (lg_avg[stat] / lg_avg[appearances]) * settings["regression_pa"][stat]
            pr[stat + "_denom"] += settings["regression_pa"][stat]

    # Apply projected rates out to the projected playing time
    for stat in settings["base_stats"]:
        pr[stat] = pr[stat] / pr[stat + "_denom"] * pr[appearances]

    # Cull out players that don't have enough playing time
    max_pa = pr[appearances].max()
    pr = pr[pr[appearances] > (max_pa * APPEARANCE_THRESHOLD)]

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

    # Scale everyone to the same PA
    if is_batting:
        pr["projected_pa"] = PROJECTED_PA
    else:
        pr["projected_pa"] = MIN_RP_BF + pr["start_pct"] * (PROJECTED_BF - MIN_RP_BF)

    pr = pr.multiply(pr["projected_pa"] / pr[appearances], axis="index")

    pr = pr[settings["display_cols"]]
    print(pr.head())

    # Add names to the data for easy readability
    pr = pr.join(load_names(), how="left")

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
    df.round().to_csv(filepath / (date + ".csv"), index_label="mlbam_id")

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
        "AB": 0.9994,
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
        "AB": 1.01,
        "R": 0.86,
        "1B": 0.91,
        "2B": 0.90,
        "3B": 0.76,
        "HR": 0.86,
        "RBI": 0.85,
        "SB": 0.85,
        "CS": 1.00,
        "BB": 0.89,
        "SO": 0.94,
        "UIBB": 0.89,
        "IBB": 0.89,
        "HBP": 0.89,
        "SH": 0.89,
        "SF": 0.89,
        "GIDP": 0.89,
    },
    "aa_factors": {
        "AB": 1.01,
        "R": 0.89,
        "1B": 0.90,
        "2B": 0.95,
        "3B": 0.95,
        "HR": 0.82,
        "RBI": 0.86,
        "SB": 0.84,
        "CS": 0.97,
        "BB": 0.89,
        "SO": 0.99,
        "UIBB": 0.89,
        "IBB": 0.89,
        "HBP": 0.89,
        "SH": 0.89,
        "SF": 0.89,
        "GIDP": 0.89,
    },
    "high_a_factors": {
        "AB": 1.02,
        "R": 0.90,
        "1B": 0.89,
        "2B": 0.97,
        "3B": 0.82,
        "HR": 1.03,
        "RBI": 0.88,
        "SB": 0.85,
        "CS": 0.89,
        "BB": 0.86,
        "SO": 1.02,
        "UIBB": 0.86,
        "IBB": 0.86,
        "HBP": 0.86,
        "SH": 0.86,
        "SF": 0.86,
        "GIDP": 0.86,
    },
    "low_a_factors": {
        "AB": 1.04,
        "R": 0.81,
        "1B": 0.83,
        "2B": 0.85,
        "3B": 0.79,
        "HR": 1.03,
        "RBI": 0.78,
        "SB": 0.71,
        "CS": 0.92,
        "BB": 0.74,
        "SO": 1.13,
        "UIBB": 0.74,
        "IBB": 0.74,
        "HBP": 0.74,
        "SH": 0.74,
        "SF": 0.74,
        "GIDP": 0.74,
    },
    "rookie_factors": {
        "AB": 1.06,
        "R": 0.60,
        "1B": 0.73,
        "2B": 0.82,
        "3B": 0.59,
        "HR": 0.55,
        "RBI": 0.59,
        "SB": 0.61,
        "CS": 0.82,
        "BB": 0.62,
        "SO": 1.21,
        "UIBB": 0.62,
        "IBB": 0.62,
        "HBP": 0.62,
        "SH": 0.62,
        "SF": 0.62,
        "GIDP": 0.62,
    },
    "fall_factors": {
        "AB": 1.04,
        "R": 0.85,
        "1B": 0.95,
        "2B": 1.09,
        "3B": 0.77,
        "HR": 1.06,
        "RBI": 0.78,
        "SB": 0.74,
        "CS": 1.00,
        "BB": 0.66,
        "SO": 0.93,
        "UIBB": 0.66,
        "IBB": 0.66,
        "HBP": 0.66,
        "SH": 0.66,
        "SF": 0.66,
        "GIDP": 0.66,
    },
}

PITCHING = {
    "display_cols": [
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
    "base_stats": [
        "W",
        "L",
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
        "W": 0.998,
        "L": 0.999,
        "G": 0.999,
        "GS": 0.999,
        "CG": 0.999,
        "SHO": 0.999,
        "SV": 0.997,
        "HLD": 0.997,
        "H": 0.9955,
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
        "G": 200,
        "GS": 200,
        "CG": 200,
        "SHO": 200,
        "SV": 100,
        "HLD": 100,
        "H": 600,
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
        "W": 0.99,
        "L": 1.44,
        "G": 1.00,
        "GS": 1.00,
        "CG": 1.00,
        "SHO": 1.00,
        "SV": 0.89,
        "HLD": 0.89,
        "H": 1.11,
        "ER": 1.15,
        "R": 1.15,
        "HR": 1.37,
        "SO": 0.59,
        "BB": 1.03,
        "UIBB": 1.03,
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
        "H": 1.14,
        "ER": 1.26,
        "R": 1.26,
        "HR": 1.48,
        "SO": 0.58,
        "BB": 1.08,
        "UIBB": 1.08,
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
        "H": 1.19,
        "ER": 1.37,
        "R": 1.37,
        "HR": 2.20,
        "SO": 0.56,
        "BB": 1.11,
        "UIBB": 1.11,
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
        "H": 1.30,
        "ER": 1.59,
        "R": 1.59,
        "HR": 3.13,
        "SO": 0.44,
        "BB": 1.11,
        "UIBB": 1.11,
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
        "H": 1.26,
        "ER": 1.33,
        "R": 1.33,
        "HR": 1.98,
        "SO": 0.45,
        "BB": 0.98,
        "UIBB": 0.98,
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
        "H": 1.25,
        "ER": 1.25,
        "R": 1.25,
        "HR": 2.03,
        "SO": 0.55,
        "BB": 0.81,
        "UIBB": 0.81,
        "IBB": 0.81,
        "HBP": 0.81,
        "WP": 0.81,
        "BK": 0.81,
    },
}


if __name__ == "__main__":
    main()
