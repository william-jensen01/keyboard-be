from flask import Blueprint, request, jsonify

from src.util import get_all_post_data, get_page_posts_small_data, get_post_data, check_post

api = Blueprint('api', __name__)

@api.route('/')
def index():
    return jsonify({'message': 'Up and well', 'ip': request.remote_addr}), 200
    
# update db by post_type
@api.route('/update/<post_type>')
def update(post_type):
    post_type = post_type.upper()
    url = ''

    def scrape_posts(url):
        page_small_data = get_page_posts_small_data(url)
        for small_post_data in page_small_data:
            post_data = get_post_data(small_post_data['url'])
            all_post_data = get_all_post_data(small_post_data, post_data)
            value = check_post(all_post_data)
            if value == 1:
                break
    
    if post_type == 'IC' or post_type == 'GB' or post_type == 'DB':
        if post_type == 'IC':
            print('Working on IC')
            url = 'https://geekhack.org/index.php?board=132.0'
            scrape_posts(url)

        if post_type == 'GB':
            print('Working on GB')
            url = 'https://geekhack.org/index.php?board=70.0'
            scrape_posts(url)

        if post_type == 'DB':
            update('IC')
            update('GB')
    else:
        res = jsonify({'message': f"Invalid post_type: {post_type}"})
        res.status_code = 400
        return res

    return jsonify({'message': f"Successfully updated {post_type}."})
