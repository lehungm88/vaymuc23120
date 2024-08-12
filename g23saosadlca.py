!pip install supabase
import requests
import re
import time
from supabase import create_client, Client

# Supabase credentials
SUPABASE_URL = 'https://vwaspnoncnkvdgqpijdl.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ3YXNwbm9uY25rdmRncXBpamRsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTkxMDkwMDQsImV4cCI6MjAzNDY4NTAwNH0.YGMbUWKgBzj-I3Z49dBr0Dm_tu5bhs0vSh4BWFZCXxI'
table_name = 'udemy_id'  # Replace with your actual table name

# Initialize Supabase client
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_course_id(url):
    """Extracts the course ID from a Udemy course URL."""
    max_retries = 3  # Set the maximum number of retries
    retries = 0
    while retries < max_retries:
        response = requests.get(url)
        if response.status_code == 200:
            html_content = response.text
            match = re.search(r'&quot;course_id&quot;:(\d+),', html_content)
            if match:
                return match.group(1)
            else:
                print("Course ID not found in response. Retrying...")
        else:
            print(f"Request failed with status code: {response.status_code}. Retrying...")
        retries += 1
        time.sleep(2)  # Wait for 2 seconds before retrying
    print("Max retries reached. Unable to extract course ID.")
    return None  # Return None if course ID is not found after retries

def process_udemy_urls(api_url):
    """Fetches Udemy course URLs, extracts coupon codes,
       modifies URLs, and retrieves course IDs.
    """
    unique_urls = set()

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        for course in data['results']:
            url = course['url']
            if "udemy" in url:
                match = re.search(r"RD_PARM1=(.+)", url)
                if match:
                    url = match.group(1)

                # 1. Extract couponCode
                coupon_match = re.search(r"couponCode=([^&]+)", url)
                coupon_code = coupon_match.group(1) if coupon_match else None

                # 2. Modify URL (remove couponCode)
                url = url.split("?couponCode=")[0]

                # 3. Get course ID
                course_id = extract_course_id(url)

                # Check if course_id already exists in the database
                if course_id:
                    response = supabase_client.table(table_name).select('udemy_id').eq('udemy_id', course_id).execute()
                    if len(response.data) == 0:
                        unique_urls.add((url, coupon_code, course_id))

        return unique_urls

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return set()


def udemy_checkout(url, coupon, course_id, cookies):
    checkout_url = "https://www.udemy.com/payment/checkout-submit/"
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookies
    }
    payload = {
        "checkout_environment": "Marketplace",
        "checkout_event": "Submit",
        "shopping_info": {
            "items": [
                {
                    "discountInfo": {
                        "code": coupon
                    },
                    "price": {
                        "amount": 0,
                        "currency": "VND"
                    },
                    "buyable": {
                        "id": course_id,
                        "type": "course"
                    }
                }
            ],
            "is_cart": False
        },
        "payment_info": {
            "method_id": "0",
            "payment_vendor": "Free",
            "payment_method": "free-method"
        },
        "tax_info": {
            "tax_rate": 5,
            "billing_location": {
                "country_code": "VN",
                "secondary_location_info": None
            },
            "currency_code": "vnd",
            "transaction_items": [
                {
                    "tax_included_amount": 0,
                    "tax_excluded_amount": 0,
                    "tax_amount": 0,
                    "udemy_txn_item_reference": f"course-{course_id}",
                    "quantity": 1
                }
            ],
            "tax_breakdown_type": "tax_inclusive"
        }
    }

    max_retries = 3  # Set maximum retries for checkout
    retries = 0
    while retries < max_retries:
        response = requests.post(checkout_url, headers=headers, json=payload)
        if response.status_code == 200:
            print("Checkout request successful:", response.text)
            if "succeeded" in response.text or "You have already subscribed" in response.text:
                supabase_client.table('udemy_id').upsert({'udemy_id': course_id}).execute()
            return  # Exit the loop if checkout is successful
        elif response.status_code == 429 or "Request was throttled" in response.text:
            print("Rate limited. Waiting for 60 seconds before retrying...")
            time.sleep(40)  # Wait for 60 seconds before retrying
            retries += 1
        else:
            print(f"Checkout request failed with status code: {response.status_code}")
            print(response.text)
            retries += 1

    print("Max retries reached for checkout. Unable to complete checkout.")

if __name__ == "__main__":
    api_url = "https://www.real.discount/api-web/all-courses/?store=Udemy&page=1&per_page=500&orderby=date&free=1"
    course_data = process_udemy_urls(api_url)

    if course_data:
        print("Udemy Course Data:")
        for url, coupon, course_id in course_data:
            print(f"URL: {url}")
            print(f"Coupon Code: {coupon}")
            print(f"Course ID: {course_id}")
            print("-" * 20)

            # Get your updated cookies from the browser
            updated_cookies = "client_id=bd2565cb7b0c313f5e9bae44961e8db2; access_token=\"ymVIEcMg21ROT8K2dn2WsrEDqnOqNTABIzkPlt/MK0Q:zdpPIH8G9+Ssd7wqBBYHu8AhsIV/FoAD9rknL5dV2Pw\"; csrftoken=OWRBX5sGEbe3b5Fi7kPb1TXU7lua7gmR"

            # Call the checkout function
            time.sleep(1)
            udemy_checkout(url, coupon, course_id, updated_cookies)

    else:
        print("No Udemy course data found.")