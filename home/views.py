from typing import Any
from django.shortcuts import render
from pymongo import MongoClient
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from fuzzywuzzy import fuzz  
from django.http import HttpResponse
from datetime import datetime  
from django.db.models import Q
from django.http import JsonResponse

import re
import json
import logging
import nltk
import random
from bson.json_util import dumps



# Initialize NLTK stopwords
nltk.download("stopwords")
from nltk.corpus import stopwords
stop_words = set(stopwords.words("english"))

logger = logging.getLogger(__name__)


# Connect to MongoDB
client = MongoClient('mongodb+srv://capstonesummer1:9Q8SkkzyUPhEKt8i@cluster0.5gsgvlz.mongodb.net/')
db = client['Product_Comparison_System']
collection = db['Sept_FInal_Final']



def search(request):
    search_query = request.GET.get('search_query', '')
    # Assuming product ID is stored under 'id' field in MongoDB
    search_results_list = list(collection.find({"title": {"$regex": search_query, "$options": "i"}}))
    # Create a list of products that includes id for each product
    products = [{'id': item['id'], 'title': item['title']} for item in search_results_list] if search_results_list else []
    return JsonResponse({'search_results': products})
# def search(request):
#     search_query = request.GET.get('search_query', '')

#     # Assuming product ID is stored under 'id' field in MongoDB
#     search_results_list = list(collection.find({"title": {"$regex": search_query, "$options": "i"}}))

#     # Create a list of products that includes id for each product
#     products = [{'id': item['id'], 'title': item['title']} for item in search_results_list] if search_results_list else []

#     context = {
#       'search_results': products,  
#     }

#     return render(request, 'includes/search.html', context)



def home(request):
    product_details_list = {}
     # Fetch data from MongoDB
    categories = collection.distinct('category')
    for category in categories:
        products = collection.find({'category': category})
        product_details_list[category] = list(products)

    # Create a list to store the randomly selected products
    random_shopmetro = []
    random_waltermart = []
    random_puregold = []
    # Loop through the categories and select a random product from each category
    for category, products in product_details_list.items():
        if products:
            random_products = random.sample(products, 5)  # Select 4 random products
            for product in random_products:
                if product['supermarket'] == 'ShopMetro':
                    random_shopmetro.append(product)
                elif product['supermarket'] == 'WalterMart':
                    random_waltermart.append(product)
                elif product['supermarket'] == 'Puregold':
                    random_puregold.append(product)

    # Shuffle the lists to randomize their order
    random.shuffle(random_shopmetro)
    random.shuffle(random_waltermart)
    random.shuffle(random_puregold)
 
    random_discount = []
    random.shuffle(random_discount)
    random_discount = random_discount[:7]

    for category, products in product_details_list.items():
        discounted_products = [product for product in products if product.get('discounted_price')]
        if discounted_products:
            random_product = random.choice(discounted_products)
            random_discount.append(random_product)

     # Sorting based on the 'sort' query parameter
    sort_option = request.GET.get('sort')
    for category, products in product_details_list.items():
        product_details_list[category] = sort_products(products, sort_option)

    context = {
        'product_details_list': product_details_list,
        'random_shopmetro': random_shopmetro,
        'random_waltermart': random_waltermart,
        'random_puregold': random_puregold,        
        'random_discount': random_discount,  # Add the new random products with discounted prices
    }
    return render(request, 'index.html', context)

def category(request, category_name):
    # Retrieve products for the specified category from MongoDB
    products = list(collection.find({'category': category_name}))  # Convert cursor to list

    # Get the selected sorting option from the URL query parameters
    sort_option = request.GET.get('sort')

    # Get the selected price range from the URL query parameters
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    # Get the selected supermarket from the URL query parameters
    selected_supermarket = request.GET.get('supermarket')

    # Filter products based on the selected price range
    if min_price is not None and max_price is not None:
        min_price = float(min_price)
        max_price = float(max_price)
        products = [product for product in products if min_price <= get_price(product) <= max_price]

    # Filter products based on the selected supermarket (if provided)
    if selected_supermarket and selected_supermarket != 'None':
        products = [product for product in products if product['supermarket'] == selected_supermarket]

    # Determine the sorting key based on the selected option
    if sort_option == 'price_low_to_high':
        sorting_key = 'discounted_price'  # Sort by discounted price ascending
    elif sort_option == 'price_high_to_low':
        sorting_key = '-discounted_price'  # Sort by discounted price descending
    else:
        sorting_key = None  # Default: No sorting

    if sorting_key:
        # Sort the entire list of products based on the sorting key
        products = sort_products(products, sort_option)

    # Calculate the total number of products for the selected category
    total_products = len(products)

    # Create a Paginator object with 20 products per page
    paginator = Paginator(products, 20)

    # Get the requested page number from the URL query parameters~
    page = request.GET.get('page')

    try:
        # Try to get the products for the requested page
        product_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, default to page 1~
        product_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g., page 9999), deliver the last page of results
        product_page = paginator.page(paginator.num_pages)

    # Implement sorting and price filtering as needed (similar to your current code)

    context = {
        'product_page': product_page,  # Pass the paginated products to the template
        'total_products': total_products,  # Pass the total number of products for the selected category
        'sort_option': sort_option,  # Pass the selected sorting option to the template
        'category_name': category_name,
        'min_price': min_price,  # Pass the selected min price to the template
        'max_price': max_price,
        'selected_supermarket': selected_supermarket,  # Pass the selected supermarket to the template
    }

    return render(request, 'category.html', context)

def get_price(product):
    # Try to get the discounted price, then the original price, and default to None if both are missing
    price_str = product.get('discounted_price') or product.get('original_price')

    if price_str:
        # Remove non-numeric characters and spaces from the price string
        cleaned_price_str = re.sub(r'[^\d.]', '', price_str)

        if cleaned_price_str:
            # Try to convert the cleaned price string to a float
            return float(cleaned_price_str)

    # Return None if price information is missing or cannot be converted
    return None

def sort_products(products, sort_option):
    # Filter out products with None prices before sorting
    products = [product for product in products if get_price(product) is not None]

    if sort_option == 'price_low_to_high':
        sorted_products = sorted(products, key=lambda x: get_price(x))
    elif sort_option == 'price_high_to_low':
        sorted_products = sorted(products, key=lambda x: get_price(x), reverse=True)
    else:
        sorted_products = products  # Default: no sorting

    return sorted_products


# Preprocess text: remove stopwords, punctuation, and extra spaces
def preprocess_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = " ".join([word for word in text.split() if word not in stop_words])  # Remove stopwords
    return text

def extract_weight(title):
    # Define regular expression patterns to match various weight/quantity units
    weight_patterns = [
        r'\b\d+\s*(?:g|grams|kg|kilograms|oz|ounces|lb|pounds)\b',
        r'\b\d+\s*(?:ml|milliliters)\b',
    ]

    for pattern in weight_patterns:
        # Search for the pattern in the title
        weight_match = re.search(pattern, title, re.IGNORECASE)

        if weight_match:
            return weight_match.group()

    # If no matching pattern is found, return None
    return None


# Calculate similarity using TF-IDF and Cosine Similarity
def calculate_similarity(input_title, product_titles):
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform([input_title] + product_titles)
    cosine_similarities = linear_kernel(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    return cosine_similarities

# Find similar products based on similarity scores within a threshold range
def find_similar_products(title):
    product_titles = [p.get('title', '') for p in collection.find()]

    # Split the input title into product name and weight/grams
    input_title_parts = re.split(r'\s+\|\s+', title)
    input_name = input_title_parts[0]
    input_weight = input_title_parts[-1]

    # Preprocess input title parts
    input_name = preprocess_text(input_name)
    input_weight = preprocess_text(input_weight)

    title_parts_list = [re.split(r'\s+\|\s+', product_title) for product_title in product_titles]
    product_names = [preprocess_text(parts[0]) for parts in title_parts_list]
    product_weights = [preprocess_text(parts[-1]) for parts in title_parts_list]

    # Fetch the category names
    product_categories = [p.get('category', '') for p in collection.find()]

    similarity_scores = calculate_similarity(input_name, product_names)

    similar_products = []
    for i, score in enumerate(similarity_scores):
        if 0.50 <= score <= 0.9:  # Adjust the threshold range as needed
            # Check if the weight/grams are similar
            if fuzz.ratio(input_weight, product_weights[i]) >= 80:  # Adjust the similarity threshold as needed
                product_doc = collection.find()[i]  # Get the MongoDB document
                similar_products.append({
                    'title': product_titles[i],
                    'supermarket': product_doc.get('supermarket', ''),  # Fetch the 'supermarket' field
                    'original_price': product_doc.get('original_price', ''),  # Fetch the 'original_price' field
                    'url': product_doc.get('url', ''),  # Fetch the 'url' field
                    'similarity_score': score,
                    'category': product_categories[i],  # Add the category name
                })

    similar_products.sort(key=lambda x: x['similarity_score'], reverse=True)

    return similar_products


# Modify the product_detail view to find similar products
def product_detail(request, product_id):
    product = collection.find_one({'id': product_id})

    # Get the product title
    product_title = product.get('title', '')

    # Use the find_similar_products function to find similar products
    similar_products = find_similar_products(product_title)

    # Get the historical price data for the product
    price_history = product.get('price_history', [])

    # Format the date in the price history data
    formatted_price_history = []
    for entry in price_history:
        date_scraped = entry.get('date_scraped')
        if date_scraped:
            # Parse the date from ISO format
            date_object = datetime.fromisoformat(date_scraped)

            # Format the date as "Month Year"
            formatted_date = date_object.strftime('%B %Y')

            # Create a new entry with the formatted date
            formatted_entry = {
                'price': entry.get('price', ''),
                'date_scraped': formatted_date,
            }

            formatted_price_history.append(formatted_entry)

    # Serialize the formatted price history data to JSON
    formatted_price_history_json = json.dumps(formatted_price_history)

    # Log the price data to the console for debugging
    logging.debug(f'Product ID: {product_id}, Price History: {formatted_price_history}')

    context = {
        'product': product,
        'similar_products': similar_products,  # Pass the list of similar products to the template
        'formatted_price_history_json': formatted_price_history_json,
        'has_price_history': bool(formatted_price_history),  # Check if price history exists
    }
    return render(request, 'product_detail.html', context)



def discounts(request):
    # Fetch all products with a discounted price from MongoDB
    discounted_products = list(collection.find({'discounted_price': {'$exists': True}}))

    # Get the selected supermarket from the URL query parameters
    selected_supermarket = request.GET.get('supermarket')

    # Filter products based on the selected supermarket (if provided)
    if selected_supermarket and selected_supermarket != 'None':
        discounted_products = [product for product in discounted_products if product['supermarket'] == selected_supermarket]


    # Create a Paginator object with 15 products per page
    paginator = Paginator(discounted_products, 15)

    # Get the requested page number from the URL query parameters
    page = request.GET.get('page')

    try:
        # Try to get the products for the requested page
        product_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, default to page 1
        product_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver the last page of results
        product_page = paginator.page(paginator.num_pages)

    context = {
        'discounted_products': product_page,
        'selected_supermarket': selected_supermarket,
    }

    return render(request, 'discounts.html', context)


def chart(request):
    # You can add any context data if needed
    context = {
        'example_data': 'Hello from the new template!',
    }

    return render(request, 'chart.html', context)



