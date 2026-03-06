from flask import Flask, render_template, send_from_directory

app = Flask(__name__)


@app.route("/tiktokmYW5VHluS2PcrCxUS646CWf1TCNmsqzG.txt")
def tiktok_verification():
    return "tiktok-developers-site-verification=mYW5VHluS2PcrCxUS646CWf1TCNmsqzG", 200, {"Content-Type": "text/plain"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
