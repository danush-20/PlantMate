from flask import Flask, render_template, request, redirect, url_for
import requests
import os
from dotenv import load_dotenv

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Load environment variables from .env file
load_dotenv('.env')
API_KEY = os.getenv('API_KEY')
API_URL = os.getenv('API_URL')

WIKIPEDIA_API_URL = 'https://en.wikipedia.org/w/api.php'

GBIF_API_URL = os.getenv('GBIF_API_URL')
DETAILS_URL = os.getenv('DETAILS_URL')

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_SEARCH_URL = os.getenv('YOUTUBE_SEARCH_URL')

def get_plant_details_wikipedia(plant_name):
    try:
        params = {
            'action': 'query',
            'format': 'json',
            'titles': plant_name,
            'prop': 'extracts',
            'exintro': True,
            'explaintext': True,
        }
        response = requests.get(WIKIPEDIA_API_URL, params=params)
        response.raise_for_status()
        pages = response.json().get('query', {}).get('pages', {})
        for _, page_data in pages.items():
            return page_data.get('extract', 'No details found.')
    except requests.exceptions.RequestException as e:
        return f"Error fetching details: {str(e)}"


def get_plant_details(plant_name):
    try:
        response = requests.get(GBIF_API_URL, params={"name": plant_name, "verbose": "true"})
        response.raise_for_status()
        data = response.json()
        if "scientificName" in data:
            species_key = data.get("usageKey", "N/A")
            details = {
                "Scientific Name": data.get("scientificName", "N/A"),
                "Kingdom": data.get("kingdom", "N/A"),
                "Phylum": data.get("phylum", "N/A"),
                "Class": data.get("class", "N/A"),
                "Order": data.get("order", "N/A"),
                "Family": data.get("family", "N/A"),
                "Genus": data.get("genus", "N/A"),
                "More Info": f"https://www.gbif.org/species/{species_key}"
            }
            if species_key != "N/A":
                common_name_response = requests.get(DETAILS_URL.format(species_key))
                if common_name_response.status_code == 200:
                    common_name = common_name_response.json().get("vernacularName", "N/A")
                    details["Common Name"] = common_name
            return details
    except requests.exceptions.RequestException as e:
        return {"Error": str(e)}
    return {"Error": "No plant found."}

def get_plant_videos(plant_name):
    params = {
        "part": "snippet",
        "q": f"how to grow {plant_name}",
        "key": YOUTUBE_API_KEY,
        "maxResults": 3,
        "type": "video"
    }
    
    response = requests.get(YOUTUBE_SEARCH_URL, params=params)

    if response.status_code == 200:
        data = response.json()
        videos = data.get("items", [])
        return [{"title": v["snippet"]["title"], "videoId": v["id"]["videoId"]} for v in videos]
    return []



@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            return "No file part"

        file = request.files["file"]
        if file.filename == "":
            return "No selected file"

        if file:
            # Save uploaded image
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            # Send image to Plant.id API
            with open(file_path, "rb") as image_file:
                files = {"images": image_file}
                headers = {"Api-Key": API_KEY}
                response = requests.post(API_URL, files=files, headers=headers)

            if response.status_code == 201:
                result = response.json()
                suggestions = result.get("result", {}).get("classification", {}).get("suggestions", [])

                # Get the top suggested plant name
                if suggestions:
                    top_suggestion = suggestions[0].get("name", "Unknown")
                    probability = float(suggestions[0].get("probability", 0) or 0)  # Corrected this line
                else:
                    top_suggestion = "No suggestions found"
                    probability = 0


                # Redirect to the result page
                return redirect(url_for("result", image=file.filename, plant_name=top_suggestion, probability=probability))

    return render_template("index.html")

@app.route("/result")
def result():
    image = request.args.get("image")
    plant_name = request.args.get("plant_name")
    probability = request.args.get("probability")
    probability = round(float(probability) * 100,2)
    image_url = os.path.join("static/uploads", image) if image else None
    return render_template("result.html", image_url=image_url, plant_name=plant_name, probability=probability)


@app.route('/plant-details')
def plant_details():
    plant_name = request.args.get('plant_name', 'Unknown')
    details = get_plant_details(plant_name)
    wiki_details = get_plant_details_wikipedia(plant_name)
    details = get_plant_details(plant_name)
    if wiki_details == "":
        wiki_details = get_plant_details_wikipedia(details['Common Name'])
        if wiki_details == "":
            wiki_details = 'No details found.'
    return render_template("plantdetails.html", plant_name=plant_name, details=details, wiki_details=wiki_details)


@app.route("/videos", methods=["GET", "POST"])
def videos():
    videos = []
    plant_name = request.args.get('plant_name', 'Unknown')
    details = get_plant_details(plant_name)
    videos = get_plant_videos(details['Common Name'])
    return render_template("videos.html", videos=videos)


if __name__ == "__main__":
    app.run(debug=True)
