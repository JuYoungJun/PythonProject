import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import os
import json
import time
import smtplib
from email.mime.text import MIMEText
from jinja2 import Template

def send_email(subject, body, to_email):
    """
    429 오류 발생 시 이메일로 알림을 보냅니다.

    Args:
        subject (str): 이메일 제목
        body (str): 이메일 내용
        to_email (str): 수신 이메일 주소
    """
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("이메일 환경 변수가 설정되지 않았습니다.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())

def get_top_tracks_and_albums_by_country(client_id, client_secret, country_code):
    """
    Spotify API를 사용하여 특정 국가의 상위 트랙 및 앨범 데이터를 최대한 많이 가져옵니다.

    Args:
        client_id (str): Spotify API 클라이언트 ID.
        client_secret (str): Spotify API 클라이언트 시크릿.
        country_code (str): ISO 3166-1 alpha-2 국가 코드.

    Returns:
        pd.DataFrame: 해당 국가의 상위 트랙 및 앨범 데이터를 포함한 DataFrame.
    """
    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    data = []
    offset = 0
    limit = 50

    try:
        # Fetch tracks from featured playlists
        while True:
            playlist_results = sp.featured_playlists(locale=country_code, limit=1)
            playlists = playlist_results.get('playlists', {}).get('items', [])

            if not playlists:
                break

            for playlist in playlists:
                playlist_tracks = sp.playlist_tracks(playlist_id=playlist['id'], limit=limit, offset=offset)
                for track_item in playlist_tracks['items']:
                    track = track_item['track']
                    data.append({
                        'Country': country_code,
                        'Type': 'Track',
                        'Track Name': track['name'],
                        'Artist Name': ", ".join([artist['name'] for artist in track['artists']]),
                        'Album Name': track['album']['name'],
                        'Release Date': track['album']['release_date'],
                        'Popularity': track['popularity'],
                        'Spotify URL': track['external_urls']['spotify']
                    })
            offset += limit

        # Fetch albums
        offset = 0
        while True:
            album_results = sp.new_releases(country=country_code, limit=limit, offset=offset)
            albums = album_results.get('albums', {}).get('items', [])

            if not albums:
                break

            for album in albums:
                data.append({
                    'Country': country_code,
                    'Type': 'Album',
                    'Track Name': None,
                    'Artist Name': ", ".join([artist['name'] for artist in album['artists']]),
                    'Album Name': album['name'],
                    'Release Date': album['release_date'],
                    'Popularity': sp.album(album['id'])['popularity'],
                    'Spotify URL': album['external_urls']['spotify']
                })
            offset += limit

        return pd.DataFrame(data)

    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 429:
            print(f"429 Too Many Requests: {e}")
            send_email("Spotify API Error", "429 Too Many Requests 발생. 일정 시간 후 재시도합니다.", os.getenv("RECIPIENT_EMAIL"))
            retry_after = int(e.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            return get_top_tracks_and_albums_by_country(client_id, client_secret, country_code)
        else:
            print(f"{country_code} 데이터를 가져오는 중 오류 발생: {e}")
            return pd.DataFrame()

def save_data_by_country(data, country):
    os.makedirs("output/json", exist_ok=True)
    os.makedirs("output/html", exist_ok=True)
    os.makedirs("output/csv", exist_ok=True)

    json_path = f"output/json/{country}_music_trends.json"
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(data.to_dict(orient="records"), json_file, ensure_ascii=False, indent=4)

    html_path = f"output/html/{country}_music_trends.html"
    html_template = Template('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ country }} Music Trends</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f4f4f4; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
        </style>
    </head>
    <body>
        <h1>{{ country }} Music Trends</h1>
        <table>
            <thead>
                <tr>
                    {% for col in data.columns %}
                    <th>{{ col }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in data.values %}
                <tr>
                    {% for cell in row %}
                    <td>{{ cell }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    ''')
    with open(html_path, "w", encoding="utf-8") as html_file:
        html_file.write(html_template.render(country=country, data=data))

    csv_path = f"output/csv/{country}_music_trends.csv"
    data.to_csv(csv_path, index_label="Rank", encoding="utf-8-sig", lineterminator="\n")

def get_all_supported_countries():
    return ["AD", "AR", "AU", "AT", "BE", "BR", "CA", "CL", "CO", "CR", "CY", "CZ", "DK", "DO", "EC", "FI", "FR", "DE", "GR", "HK", "HU", "IS", "ID", "IE", "IL", "IT", "JP", "LV", "LI", "LT", "LU", "MY", "MT", "MX", "NL", "NZ", "NO", "PH", "PL", "PT", "SG", "ES", "SE", "CH", "TW", "TR", "GB", "US", "UY", "VN", "KR"]

if __name__ == "__main__":
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    countries = get_all_supported_countries()

    for country in countries:
        print(f"{country} 데이터를 가져오는 중...")
        country_data = get_top_tracks_and_albums_by_country(CLIENT_ID, CLIENT_SECRET, country)

        if not country_data.empty:
            country_data = country_data.sort_values(by=['Popularity'], ascending=False)
            country_data = country_data.reset_index(drop=True)
            country_data.index += 1
            save_data_by_country(country_data, country)

    print("모든 데이터 수집 및 저장 완료.")
