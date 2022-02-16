from flask import Flask, request, render_template

import pandas as pd
import json

import build_logs
import blyleven as project2
import campanella as project3

app = Flask(__name__, static_folder="assets")

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/stats/<int:year>', methods=['PUT'])
def put_year_stats(year):
    build_logs.build_yearly_gamelogs(year)
    build_logs.combine_gamelogs()
    return "Built logs for " + str(year)

@app.route('/stats/<int:year>/<int:month>', methods=['PUT'])
def put_month_stats(year, month):
    build_logs.build_monthly_gamelogs(year, month)
    build_logs.combine_gamelogs()
    return "Built logs for " + str(year) + "-" + str(month)

@app.route('/stats/<int:year>/<int:month>/<int:day>', methods=['PUT'])
def put_day_stats(year, month, day):
    date_string = str(year) + "-" + str(month).zfill(2) + "-" + str(day).zfill(2)
    build_logs.build_daily_gamelogs(date_string)
    build_logs.combine_gamelogs()
    return "Built logs for " + date_string

@app.route('/projections/<string:date_string>', methods=['PUT'])
def put_projections(date_string):
    project2.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/projections/<string:date_string>', methods=['GET'])
def get_projections(date_string):

    batting_df = project3.load_projection(date_string, True)
    pitching_df = project3.load_projection(date_string, False)

    numeric_cols = batting_df.select_dtypes(include="number")
    batting_df[numeric_cols.columns] = numeric_cols.astype(int)
    numeric_cols = pitching_df.select_dtypes(include="number")
    pitching_df[numeric_cols.columns] = numeric_cols.astype(int)

    batting_html = batting_df.to_html(classes="table is-hoverable sortable", index=False)
    pitching_html = pitching_df.to_html(classes="table is-hoverable sortable", index=False)

    return render_template("projections.html", batting=batting_html, pitching=pitching_html, date_string=date_string)


@app.route('/v3/projections/<string:date_string>', methods=['PUT'])
def put_v3_projections(date_string):
    project3.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/v3/projections/<string:date_string>', methods=['GET'])
def get_v3_projections(date_string):
    if (request.args.get("type") == "batting"):
        is_batting = True
    elif (request.args.get("type") == "pitching"):
        is_batting = False
    else:
        return "Error: type must be batting or pitching."

    df = project3.load_projection(date_string, is_batting)
    return df.to_json(orient="records")

@app.route('/v3/projections/', methods=['GET'])
def get_v3_player_projections():
    if 'playerId' in request.args:
        player_id = int(request.args['playerId'])
    else:
        return "Error: No playerId provided. Please specify an (MLBAM) id."

    data = {}

    bat = pd.DataFrame()
    bat = project3.load_player_projections(player_id, True)
    data["batting"] = bat.to_dict("records")

    pit = pd.DataFrame()
    pit = project3.load_player_projections(player_id, False)
    data["pitching"] = pit.to_dict("records")

    return json.dumps(data)

    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)