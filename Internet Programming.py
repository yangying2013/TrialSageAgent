import requests

API_KEY = "your_api_key_here"
API_BASEURL = "https://api.example.com/articles"

def search_articles(search_term):
    params = {
        'q': search_term,
        'apiKey': API_KEY
    }
    response = requests.get(API_BASEURL, params=params)
    return response.json()




def display_results(search_results):
    print("\nSearch Results:")
import requests

while True:
    search_term = input(" Your search term (type 'exit' to quit): ")
    if search_term.lower() == 'exit':
        break
    search_results = search.articles(search_term)