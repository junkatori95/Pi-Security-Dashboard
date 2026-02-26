import face_recognition
import pickle

# 1. Load your photo (Make sure 'owner.jpg' is in the same folder)
image = face_recognition.load_image_file("owner.jpg")

# 2. Convert the photo into a numerical encoding
encoding = face_recognition.face_encodings(image)[0]

# 3. Save it to the 'known_faces.pkl' file the dashboard expects
data = {"Owner": encoding}

with open("known_faces.pkl", "wb") as f:
    pickle.dump(data, f)

print("? Success! 'known_faces.pkl' created. You can now run your dashboard.")
