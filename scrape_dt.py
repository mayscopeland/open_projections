import pandas as pd
import numpy as np

def main():
    
    get_all_leagues(True)
    get_all_leagues(False)

def get_all_leagues(is_batting):
    
    print(get_factors("ACL", is_batting))
    print(get_factors("FCL", is_batting))
    
    print(get_factors("LAW", is_batting))
    print(get_factors("LAS", is_batting))
    print(get_factors("LAE", is_batting))
    
    print(get_factors("HAW", is_batting))
    print(get_factors("HAC", is_batting))
    print(get_factors("HAE", is_batting))

    print(get_factors("2AS", is_batting))
    print(get_factors("2AC", is_batting))
    print(get_factors("2AN", is_batting))

    print(get_factors("3AE", is_batting))
    print(get_factors("3AW", is_batting))

def get_factors(league, is_batting):

    type = "real"
    if is_batting:
        pitching = ""
    else:
        pitching = "p"
    url = f"http://claydavenport.com/stats/webpages/2021/2021{pitching}page{league}{type}ALL.shtml"
    print(url)

    dfs = pd.read_html(url, index_col=0)
    real = dfs[1].apply(pd.to_numeric, errors="coerce")
    real = rename_cols(real, is_batting)

    if is_batting:
        real = real[real["AB"] >= 100]
    else:
        real = real[real["IP"] >= 20]

    type = "year"
    url = f"http://claydavenport.com/stats/webpages/2021/2021{pitching}page{league}{type}ALL.shtml"
    print(url)
    dfs = pd.read_html(url, index_col=0)
    dt = dfs[1].apply(pd.to_numeric, errors="coerce")
    dt = rename_cols(dt, is_batting)

    df = dt.merge(real, how="inner", on="Name")

    batting_stats = ["AB","H","2B","3B","HR","BB","SO","R","RBI","SB","CS"]
    pitching_stats = ["IP","H","ER","HR","BB","SO","W","L","SV"]

    if is_batting:
        stats = batting_stats
    else:
        stats = pitching_stats

    for stat in stats:
        df[stat] = np.where(df[stat+"_y"] > 0, df[stat+"_x"] / df[stat+"_y"], np.NaN)

    df = df[stats]
    return df.mean().round(2).to_dict()

def rename_cols(df, is_batting):
    
    if is_batting:
        df["2B"] = df["DB"]
        df["3B"] = df["TP"]
    else:
        df["SO"] = df["K"]
    
    return df

if __name__ == "__main__":
    main()