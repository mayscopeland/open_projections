from flask import Flask, request, render_template

import pandas as pd

import build_logs
import aparicio

app = Flask(__name__)

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
    aparicio.project_all(date_string)
    return "Projections for " + date_string + " finished"

@app.route('/projections/<string:date_string>', methods=['GET'])
def get_projections(date_string):
    if (request.args.get("type") == "batting"):
        is_batting = True
    elif (request.args.get("type") == "pitching"):
        is_batting = False
    else:
        return "Error: type must be batting or pitching."

    df = aparicio.load_projection(date_string, is_batting)
    return df.to_json(orient="records")

@app.route('/projections/', methods=['GET'])
def get_player_projections():
    if 'playerId' in request.args:
        player_id = int(request.args['playerId'])
    else:
        return "Error: No playerId provided. Please specify an (MLBAM) id."

    df = pd.DataFrame()
    df = aparicio.load_player_projections(player_id, True)

    # Did we find batting projections?
    if df.empty:
        df = aparicio.load_player_projections(player_id, False)

    return df.to_json(orient="records")

    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)