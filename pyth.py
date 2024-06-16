import sqlite3
import pandas as pd

# Step 1: Import CSV Data into SQLite3 Database with Song Names

# Load the CSV file into a pandas DataFrame
csv_file = 'inputs.csv'  # Ensure your CSV has columns: username, song_name, rating
ratings_df = pd.read_csv(csv_file)

# Create a SQLite database and connect to it
conn = sqlite3.connect('ratings.db')
cursor = conn.cursor()

# Create a table for storing ratings with song names
cursor.execute('''
CREATE TABLE IF NOT EXISTS ratings (
    username TEXT,
    song_name TEXT,
    rating INTEGER
)
''')

# Insert data from DataFrame into the ratings table
ratings_df.to_sql('ratings', conn, if_exists='replace', index=False)

# Commit the transaction and close the connection
conn.commit()
conn.close()

def add_ratings(new_ratings, db_path='ratings.db'):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert new ratings into the database
    cursor.executemany('''
    INSERT INTO ratings (username, song_name, rating) VALUES (?, ?, ?)
    ''', new_ratings)
    
    # Commit the transaction and close the connection
    conn.commit()
    conn.close()

def recommend_for_existing_users(username, db_path='ratings.db', num_recommendations=5):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    
    # Query to calculate the average rating for each song
    song_avg_query = '''
    SELECT song_name, AVG(rating) as avg_rating
    FROM ratings
    GROUP BY song_name
    '''
    song_avg_ratings = pd.read_sql(song_avg_query, conn)
    
    # Query to get the list of songs the user has already rated
    user_rated_query = '''
    SELECT song_name
    FROM ratings
    WHERE username = ?
    '''
    rated_songs = pd.read_sql(user_rated_query, conn, params=(username,))
    
    # Filter out the songs the user has already rated
    recommendations = song_avg_ratings[~song_avg_ratings['song_name'].isin(rated_songs['song_name'])]
    
    # Sort the songs by average rating in descending order
    recommendations = recommendations.sort_values(by='avg_rating', ascending=False)
    
    # Close the connection
    conn.close()
    
    # Return the top N recommendations
    return recommendations.head(num_recommendations)

def recommend_for_new_users(db_path='ratings.db', num_recommendations=5):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    
    # Query to calculate the average rating for each song
    song_avg_query = '''
    SELECT song_name, AVG(rating) as avg_rating
    FROM ratings
    GROUP BY song_name
    '''
    song_avg_ratings = pd.read_sql(song_avg_query, conn)
    
    # Sort the songs by average rating in descending order
    recommendations = song_avg_ratings.sort_values(by='avg_rating', ascending=False)
    
    # Close the connection
    conn.close()
    
    # Return the top N recommendations
    return recommendations.head(num_recommendations)

# Example usage
print("Recommendations for existing user (username=1):")
print(recommend_for_existing_users(username=1))

print("Recommendations for new users:")
print(recommend_for_new_users())
"""
# Adding new ratings
new_ratings = [(4, 'Song A', 5), (4, 'Song B', 4), (4, 'Song C', 3)]
add_ratings(new_ratings)
# Re-check recommendations for the new user
print("Updated recommendations for new users after adding new ratings:")
print(recommend_for_new_users())
"""