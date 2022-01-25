import pandas as pd
from pathlib import Path

BATTING_COLS = ["HBP","BB","SO","HR","1B","2B","3B","SB","R","RBI"]
PITCHING_COLS = ["W","L","SV","H","ER","HR","SO","BB","HBP"]

def main():
    #calc_batting()
    calc_pitching()

def calc_batting():
    # open stats and projections
    filepath = Path(__file__).parent
    stats = pd.read_csv(filepath / "2021Batting.csv")
    zips = pd.read_csv(filepath / "2021 ZiPS Batting.csv")
    steamer = pd.read_csv(filepath / "2021 Steamer Batting.csv")
    atc = pd.read_csv(filepath / "2021 ATC Batting.csv")
    bat = pd.read_csv(filepath / "2021 THE BAT Batting.csv")
    batx = pd.read_csv(filepath / "2021 THE BAT X Batting.csv")
    open = pd.read_csv(filepath / "projections" / "v3" / "batting" / "2021-04-01.csv")

    zips = calc(zips, stats, True)
    steamer = calc(steamer, stats, True)
    atc = calc(atc, stats, True)
    bat = calc(bat, stats, True)
    batx = calc(batx, stats, True)
    open = calc(open, stats, True)

    # Find correlation
    print_corr(zips, BATTING_COLS)
    print_corr(steamer, BATTING_COLS)
    print_corr(atc, BATTING_COLS)
    print_corr(bat, BATTING_COLS)
    print_corr(batx, BATTING_COLS)
    print_corr(open, BATTING_COLS)

    for col in BATTING_COLS:
        print_cat_rmse(zips, col)
        print_cat_rmse(steamer, col)
        print_cat_rmse(atc, col)
        print_cat_rmse(bat, col)
        print_cat_rmse(batx, col)
        print_cat_rmse(open, col)

def calc_pitching():
    # open stats and projections
    filepath = Path(__file__).parent
    stats = pd.read_csv(filepath / "2021Pitching.csv")
    zips = pd.read_csv(filepath / "2021 ZiPS Pitching.csv")
    steamer = pd.read_csv(filepath / "2021 Steamer Pitching.csv")
    atc = pd.read_csv(filepath / "2021 ATC Pitching.csv")
    bat = pd.read_csv(filepath / "2021 THE BAT Pitching.csv")
    open = pd.read_csv(filepath / "projections" / "v3" / "pitching" / "2021-04-01.csv")

    zips = calc(zips, stats, False)
    steamer = calc(steamer, stats, False)
    atc = calc(atc, stats, False)
    bat = calc(bat, stats, False)
    open = calc(open, stats, False)

    # Find correlation
    print_corr(zips, PITCHING_COLS)
    print_corr(steamer, PITCHING_COLS)
    print_corr(atc, PITCHING_COLS)
    print_corr(bat, PITCHING_COLS)
    print_corr(open, PITCHING_COLS)

    for col in PITCHING_COLS:
        print_cat_rmse(zips, col)
        print_cat_rmse(steamer, col)
        print_cat_rmse(atc, col)
        print_cat_rmse(bat, col)
        print_cat_rmse(open, col)


def calc(pred, act, is_batting):

    if "HBP" not in pred:
        pred["HBP"] = 0

    if is_batting:
        act["PA"] = act["AB"] + act["BB"] + act["HBP"] + act["SH"] + act["SF"]
        act["1B"] = act["H"] - act["HR"] - act["3B"] - act["2B"]
        pred["1B"] = pred["H"] - pred["HR"] - pred["3B"] - pred["2B"]
    else:
        act["IP"] = act["IP"].map(convert_ip)
        act["BFP"] = act["IP"] * 3 + act["BB"] + act["H"] + act["HBP"]

        if "BFP" not in pred:
            pred["BFP"] = pred["IP"] * 3 + pred["BB"] + pred["H"] + pred["HBP"]

        if "SV" not in pred:
            pred["SV"] = 0

    # Combine datasets
    if is_batting:
        act = act[act["PA"] > 100]
    else:
        act = act[act["BFP"] > 100]
    pred = act.merge(pred, on="mlbam_id", suffixes=(None, "_pred"))

    # Calc rates
    if is_batting:
        cols = BATTING_COLS
        pred = calc_rates(pred, cols, "PA")
    else:
        cols = PITCHING_COLS
        pred = calc_rates(pred, cols, "BFP")

    return pred


def convert_ip(ip):
    return int(ip) + (ip % 1 * 10 / 3)


def calc_rates(df, cols, denom):

    for col in cols:
        calc_rate(df, col, denom)
        adj_to_avg(df, col)

    all_cols = []
    for col in cols:
        all_cols.append(col + "%")
        all_cols.append(col + "%_pred")
        all_cols.append(col + "%_adj")
        all_cols.append(col + "%_pred_adj")

    df = df[["mlbam_id"] + all_cols]

    return df

def calc_rate(df, cat, denom):

    df[cat + "%"] = df[cat] / df[denom]
    df[cat + "%_pred"] = df[cat + "_pred"] / df[denom + "_pred"]

    return df

def adj_to_avg(df, cat):
    avg = df[cat + "%"].mean()
    df[cat + "%_adj"] = df[cat + "%"] - avg

    pred_avg = df[cat + "%_pred"].mean()
    df[cat + "%_pred_adj"] = df[cat + "%_pred"] - pred_avg

def print_cat_rmse(df, cat):

    print(cat + ": " + str(((df[cat + "%"] - df[cat + "%_pred_adj"]) ** 2).mean() ** .5))

def print_corr(df, cols):

    all_cols = []
    for col in cols:
        all_cols.append(col + "%")
        all_cols.append(col + "%_pred")
    
    corr_df = df[all_cols]
    print(corr_df.corr())


if __name__ == "__main__":
    main()
