from flask import Flask, render_template, request

import pandas as pd
import glob
import os

import build_logs
import project

app = Flask(__name__)

@app.route("/")
def index():
    return "Open Projections v. 1.0"

@app.route('/stats/<int:year>', methods=['PUT'])
def put_stats(year):
    build_logs.build_yearly_gamelogs(year)
    build_logs.combine_gamelogs()

@app.route('/stats/<int:year>/<int:month>', methods=['PUT'])
def put_stats(year, month):
    build_logs.build_monthly_gamelogs(year, month)
    build_logs.combine_gamelogs()

@app.route('/stats/<int:year>/<int:month>/<int:day>', methods=['PUT'])
def put_stats(year, month, day):
    build_logs.build_yearly_gamelogs(year+"-"+month+"-"+day)
    build_logs.combine_gamelogs()

@app.route('/projections/<string:date_string>', methods=['PUT'])
def put_projections(date_string):
    project.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/projections/<string:date_string>/', methods=['GET'])
def get_projections(date_string):
    filepath = os.path.dirname(__file__)
    batting_file = filepath + "\\projections\\" + date_string + "-batting.csv"
    df = pd.read_csv(batting_file, index_col=None, header=0)
    return df.to_json()

@app.route('/projections/', methods=['GET'])
def get_player_projections():
    if 'playerId' in request.args:
        player_id = int(request.args['playerId'])
    else:
        return "Error: No playerId provided. Please specify an (MLBAM) id."

    batting_name, bf = load_stats(player_id, True)
    pitching_name, pf = load_stats(player_id, False)

    player_name = ""
    if batting_name:
        df = bf
    else:
        df = pf

    return df.to_json()

def load_stats(player_id, is_batting):
    
    filepath = os.path.dirname(__file__)
    player = pd.DataFrame()
    player_name = ""

    if is_batting:
        filematch = filepath + "\\open_projections\\projections\\*-batting.csv"
    else:
        filematch = filepath + "\\open_projections\\projections\\*-pitching.csv"


    for filename in glob.glob(filematch):
        df = pd.read_csv(filename, index_col=0)
        if is_batting:
            df["Date"] = filename[-22:-12]
        else:
            df["Date"] = filename[-23:-13]
        if player_id in df.index:
            player = player.append(df.loc[[player_id]])
    
    if not player.empty:
        player_name = player.iloc[0]["name_first"] + " " + player.iloc[0]["name_last"]

        if is_batting:
            int_cols = ["PA","AB","H","2B","3B","HR","R","RBI","SB","CS","BB","SO","GIDP","HBP","SH","SF","IBB"]
            display_cols = ["Date","AB","H","R","HR","RBI","SB","AVG","OBP","SLG","2B","3B","BB","SO","CS","GIDP","HBP","SH","SF","IBB"]
            player["AVG"] = (player["H"] / player["AB"]).round(3)
            player["OBP"] = ((player["H"] + player["BB"] + player["HBP"]) / (player["AB"] + player["BB"] + player["HBP"] + player["SF"])).round(3)
            player["1B"] = player["H"] - player["2B"] - player["3B"] - player["HR"]
            player["SLG"] = ((player["1B"] + player["2B"]*2 + player["3B"]*3 + player["HR"]*4) / player["AB"]).round(3)
        else:
            int_cols = ["W","L","G","GS","CG","SHO","SV","HLD","IP","H","R","ER","HR","BB","IBB","SO","HBP","BK","WP","BFP"]
            display_cols = ["Date","IP","W","L","SV","SO","ERA","WHIP","R","ER","H","BB","IBB","HBP","BK","WP","G","GS","CG","SHO"]
            player["ERA"] = (player["ER"] / player["IP"] * 9).round(2)
            player["WHIP"] = ((player["BB"] + player["H"]) / player["IP"]).round(2)
        player[int_cols] = player[int_cols].astype(int)

        player["Date"] = pd.to_datetime(player["Date"], infer_datetime_format=True)
        player.sort_values(by=['Date'], inplace=True, ascending=False)
        #player["Date"] = player['Date'].dt.strftime("%b %d, %Y")
        player = player[display_cols]

    return player_name, player 

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)