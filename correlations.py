import pandas as pd
from pathlib import Path

def main():
    calc_pitching()

def calc_batting():
    # open stats and projections
    filepath = Path(__file__).parent
    stats = pd.read_csv(filepath / "2019Batting.csv")
    steamer = pd.read_csv(filepath / "steamer_hitters_2019_preseason_final.csv")
    a = pd.read_csv(filepath / "2019-04-01-AparicioBatting.csv")

    filepath = Path(__file__).parent / "projections" / "batting"
    b = pd.read_csv(filepath / "2019-04-01.csv")

    # Calc rates
    stats["PA"] = stats["AB"] + stats["BB"] + stats["HBP"] + stats["SH"] + stats["SF"]
    stats["1B"] = stats["H"] - stats["HR"] - stats["3B"] - stats["2B"]
    stats = calc_batting_rates(stats)

    steamer["mlbam_id"] = steamer["mlbamid"]
    steamer["SO"] = steamer["K"]
    steamer["1B"] = steamer["H"] - steamer["HR"] - steamer["3B"] - steamer["2B"]
    steamer = calc_batting_rates(steamer)

    a["mlbam_id"] = a["player_id"]
    a["1B"] = a["H"] - a["HR"] - a["3B"] - a["2B"]
    a = calc_batting_rates(a)

    b["1B"] = b["H"] - b["HR"] - b["3B"] - b["2B"]
    b = calc_batting_rates(b)

    # Combine datasets
    stats = stats[stats["PA"] > 300]
    steamer = stats.merge(steamer, on="mlbam_id", suffixes=(None, "_s"))
    a = stats.merge(a, on="mlbam_id", suffixes=(None, "_a"))
    b = stats.merge(b, on="mlbam_id", suffixes=(None, "_b"))

    # Find correlation
    print(steamer.corr())
    print(a.corr())
    print(b.corr())

def calc_batting_rates(df):
    
    df["HBP%"] = df["HBP"] / df["PA"]
    df["BB%"] = df["BB"] / df["PA"]
    df["SO%"] = df["SO"] / df["PA"]
    df["HR%"] = df["HR"] / df["PA"]
    df["1B%"] = df["1B"] / df["PA"]
    df["2B%"] = df["2B"] / df["PA"]
    df["3B%"] = df["3B"] / df["PA"]
    df["SB%"] = df["SB"] / df["PA"]
    df["R%"] = df["R"] / df["PA"]
    df["RBI%"] = df["RBI"] / df["PA"]

    df = df[["mlbam_id", "HBP%", "BB%", "SO%","HR%","1B%","2B%","3B%","SB%","R%","RBI%","PA"]]

    return df


def calc_pitching():
    # open stats and projections
    filepath = Path(__file__).parent
    stats = pd.read_csv(filepath / "2019Pitching.csv")
    steamer = pd.read_csv(filepath / "steamer_pitchers_2019_preseason_final.csv")
    a = pd.read_csv(filepath / "2019-04-01-AparicioPitching.csv")

    filepath = Path(__file__).parent / "projections" / "pitching"
    b = pd.read_csv(filepath / "2019-04-01.csv")


    # Calc rates
    stats["IP"] = stats["IP"].map(convert_ip)
    stats["BFP"] = stats["IP"] * 3 + stats["BB"] + stats["H"] + stats["HBP"] 
    stats = calc_pitching_rates(stats)

    steamer["mlbam_id"] = steamer["mlbamid"]
    steamer["SO"] = steamer["K"]
    steamer["SHO"] = steamer["ShO"]
    steamer["BFP"] = steamer["TBF"]
    steamer = calc_pitching_rates(steamer)

    a["mlbam_id"] = a["player_id"]
    a = calc_pitching_rates(a)

    b = calc_pitching_rates(b)

    # Combine datasets
    stats = stats[stats["BFP"] > 200]
    steamer = stats.merge(steamer, on="mlbam_id", suffixes=(None, "_s"))
    a = stats.merge(a, on="mlbam_id", suffixes=(None, "_a"))
    b = stats.merge(b, on="mlbam_id", suffixes=(None, "_b"))

    # Find correlation
    print(steamer.corr())
    print(a.corr())
    print(b.corr())

def convert_ip(ip):
    return int(ip) + (ip % 1 * 10 / 3)

def calc_pitching_rates(df):
    
    df["W%"] = df["W"] / df["BFP"]
    df["L%"] = df["L"] / df["BFP"]
    df["CG%"] = df["CG"] / df["BFP"]
    df["SHO%"] = df["SHO"] / df["BFP"]
    df["SV%"] = df["SV"] / df["BFP"]
    df["HLD%"] = df["HLD"] / df["BFP"]
    df["H%"] = df["H"] / df["BFP"]
    df["R%"] = df["R"] / df["BFP"]
    df["ER%"] = df["ER"] / df["BFP"]
    df["HR%"] = df["HR"] / df["BFP"]
    df["SO%"] = df["SO"] / df["BFP"]
    df["BB%"] = df["BB"] / df["BFP"]
    df["HBP%"] = df["HBP"] / df["BFP"]

    df = df[["mlbam_id", "W%","L%","CG%","SHO%","SV%","HLD%","H%","R%","ER%","HR%","SO%","BB%","HBP%","BFP"]]

    return df



if __name__ == "__main__":
    main()
