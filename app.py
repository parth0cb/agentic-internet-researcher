from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    url_for,
    session,
    redirect,
)
import json
from search_engine import simple_search, agentic_search

app = Flask(__name__)
app.secret_key = "VSDX1fh-ASS8gh-1083gh0"


@app.route("/")
def index():
    if not all(
        [session.get("api_key"), session.get("base_url"), session.get("language_model")]
    ):
        return redirect(url_for("get_credentials"))
    return render_template("index.html")


@app.route("/credentials", methods=["GET", "POST"])
def get_credentials():
    if request.method == "POST":
        session.clear()
        session["api_key"] = request.form["api_key"].strip()
        session["base_url"] = request.form["base_url"].strip()
        session["language_model"] = request.form["language_model"].strip()

        return redirect(url_for("index"))
    return render_template("credentials.html")


@app.route("/search/simple", methods=["POST"])
def search_simple():
    if not all(
        [session.get("api_key"), session.get("base_url"), session.get("language_model")]
    ):
        return redirect(url_for("get_credentials"))

    api_key = session.get("api_key")
    base_url = session.get("base_url")
    language_model = session.get("language_model")

    data = request.get_json()
    query = data.get("query")

    def generate():
        for item in simple_search(
            query=query,
            api_key=api_key,
            base_url=base_url,
            language_model=language_model,
        ):
            yield json.dumps(item) + "\n"

    return Response(generate(), mimetype="text/plain")


@app.route("/search/agentic", methods=["POST"])
def search_agentic():
    if not all(
        [session.get("api_key"), session.get("base_url"), session.get("language_model")]
    ):
        return redirect(url_for("get_credentials"))

    api_key = session.get("api_key")
    base_url = session.get("base_url")
    language_model = session.get("language_model")

    data = request.get_json()
    query = data.get("query", "")

    def generate():
        try:
            for item in agentic_search(
                query=query,
                api_key=api_key,
                base_url=base_url,
                language_model=language_model,
            ):
                yield json.dumps(item) + "\n"
        except Exception as e:
            yield {"type": "error", "content": str(e)}

    return Response(generate(), mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
