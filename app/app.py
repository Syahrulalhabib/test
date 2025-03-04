from flask import Flask, request, jsonify
import tensorflow as tf
import numpy as np
import joblib
import json
from PIL import Image
import os
from sklearn.neighbors import NearestNeighbors
import pandas as pd

app = Flask(__name__)

# Initialize models as None
cnn_model = None
knn_model = None
dataset = None

# Define calculator functions
def hitung_bmr_tdee(berat_badan, tinggi_badan, umur, jenis_kelamin, tingkat_aktivitas):
    """Calculate BMR and TDEE"""
    if jenis_kelamin.lower() == 'pria':
        bmr = 10 * berat_badan + 6.25 * tinggi_badan - 5 * umur + 5
    else:  # wanita
        bmr = 10 * berat_badan + 6.25 * tinggi_badan - 5 * umur - 161

    activity_multipliers = {
        "ringan": 1.375,
        "sedang": 1.55,
        "berat": 1.725
    }
    
    if tingkat_aktivitas.lower() not in activity_multipliers:
        raise ValueError("Tingkat aktivitas tidak valid. Pilih 'ringan', 'sedang', atau 'berat'.")
        
    tdee = bmr * activity_multipliers[tingkat_aktivitas.lower()]
    return bmr, tdee

def hitung_kebutuhan_makronutrien(tdee):
    """Calculate macronutrient needs"""
    kalori_karbohidrat = tdee * 0.55
    kalori_protein = tdee * 0.20
    kalori_lemak = tdee * 0.25

    gram_karbohidrat = kalori_karbohidrat / 4
    gram_protein = kalori_protein / 4
    gram_lemak = kalori_lemak / 9

    return gram_karbohidrat, gram_protein, gram_lemak

def create_knn_model(df):
    """Create and train KNN model"""
    features = df[['Karbohidrat (g)', 'Protein (g)', 'Lemak (g)']].values
    knn = NearestNeighbors(n_neighbors=5, metric='euclidean')
    knn.fit(features)
    return knn

def load_models():
    global cnn_model, knn_model, dataset
    
    try:
        # Load CNN model
        cnn_model = tf.keras.models.load_model('v1.h5', compile=False)
        cnn_model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        print("CNN model loaded successfully")
    except Exception as e:
        print(f"Error loading CNN model: {str(e)}")
        raise

    try:
        # Load dataset
        with open('dataset.json') as f:
            dataset = json.load(f)
        print("Dataset loaded successfully")
        
        # Create DataFrame from dataset
        df = pd.DataFrame(dataset)
        
        # Create and train KNN model
        knn_model = create_knn_model(df)
        print("KNN model created successfully")
        
    except Exception as e:
        print(f"Error loading dataset or creating KNN model: {str(e)}")
        raise

def predict_food(image_path):
    """Predict food from image and get nutrition info"""
    try:
        img = Image.open(image_path)
        img = img.resize((224, 224))
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)
        
        prediction = cnn_model.predict(img_array)
        predicted_class = np.argmax(prediction, axis=1)[0]
        confidence = float(np.max(prediction))
        
        food_name = dataset[predicted_class]["Nama Makanan/Minuman"]
        nutrition = {
            "kalori": dataset[predicted_class]["Kalori (kcal)"],
            "karbohidrat": dataset[predicted_class]["Karbohidrat (g)"],
            "protein": dataset[predicted_class]["Protein (g)"],
            "lemak": dataset[predicted_class]["Lemak (g)"]
        }
        return food_name, nutrition, confidence
    except Exception as e:
        print(f"Error in predict_food: {str(e)}")
        raise

def get_food_recommendations(food_features):
    """Get food recommendations using KNN model"""
    try:
        # Get nearest neighbors
        distances, indices = knn_model.kneighbors([food_features])
        
        recommendations = []
        for idx in indices[0]:
            food = dataset[idx]
            recommendations.append({
                "nama": food["Nama Makanan/Minuman"],
                "nutrition": {
                    "kalori": food["Kalori (kcal)"],
                    "karbohidrat": food["Karbohidrat (g)"],
                    "protein": food["Protein (g)"],
                    "lemak": food["Lemak (g)"]
                },
                "similarity_score": float(1 / (1 + distances[0][len(recommendations)]))
            })
        return recommendations
    except Exception as e:
        print(f"Error in get_food_recommendations: {str(e)}")
        raise

@app.route('/predict', methods=['POST'])
def predict():
    """Endpoint for food prediction from image"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    try:
        # Create temp directory if it doesn't exist
        os.makedirs('temp', exist_ok=True)
        
        file_path = os.path.join('temp', file.filename)
        file.save(file_path)
        
        food_name, nutrition, confidence = predict_food(file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        # Get food features for recommendation
        food_features = [
            nutrition["karbohidrat"],
            nutrition["protein"], 
            nutrition["lemak"]
        ]
        recommendations = get_food_recommendations(food_features)
        
        return jsonify({
            'food_name': food_name,
            'confidence': confidence,
            'nutrition': nutrition,
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/calculate', methods=['POST'])
def calculate():
    """Endpoint for calculating nutrition needs"""
    try:
        data = request.json
        required_fields = ['weight', 'height', 'age', 'gender', 'activity_level']
        
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        bmr, tdee = hitung_bmr_tdee(
            data['weight'],
            data['height'],
            data['age'],
            data['gender'],
            data['activity_level']
        )
        
        karbohidrat, protein, lemak = hitung_kebutuhan_makronutrien(tdee)
        
        return jsonify({
            'bmr': float(bmr),
            'tdee': float(tdee),
            'kebutuhan_harian': {
                'karbohidrat': float(karbohidrat),
                'protein': float(protein),
                'lemak': float(lemak)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recommend', methods=['POST'])
def recommend():
    """Endpoint for food recommendations based on nutrition values"""
    try:
        data = request.json
        required_fields = ['karbohidrat', 'protein', 'lemak']
        
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        food_features = [
            data['karbohidrat'],
            data['protein'],
            data['lemak']
        ]
        
        recommendations = get_food_recommendations(food_features)
        
        return jsonify({
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recommend-by-name', methods=['POST'])
def recommend_by_name():
    """Endpoint for food recommendations based on food name"""
    try:
        data = request.json
        if 'food_name' not in data:
            return jsonify({'error': 'Missing food_name field'}), 400
            
        # Find the food in dataset
        food_name = data['food_name'].lower()
        food_data = None
        
        for food in dataset:
            if food["Nama Makanan/Minuman"].lower() == food_name:
                food_data = food
                break
                
        if food_data is None:
            return jsonify({'error': 'Food not found in database'}), 404
            
        # Get food features
        food_features = [
            food_data["Karbohidrat (g)"],
            food_data["Protein (g)"],
            food_data["Lemak (g)"]
        ]
        
        recommendations = get_food_recommendations(food_features)
        
        return jsonify({
            'input_food': {
                'nama': food_data["Nama Makanan/Minuman"],
                'nutrition': {
                    'kalori': food_data["Kalori (kcal)"],
                    'karbohidrat': food_data["Karbohidrat (g)"],
                    'protein': food_data["Protein (g)"],
                    'lemak': food_data["Lemak (g)"]
                }
            },
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Load models before running the app
    load_models()
    app.run(debug=True, host='0.0.0.0', port=8080)
