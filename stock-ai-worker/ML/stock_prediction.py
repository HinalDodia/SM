import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
import joblib
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential, load_model
from keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_absolute_percentage_error

# user input
try:
    ticker = input("Enter Stock Ticker (e.g., AAPL, TSLA, MSFT): ").upper()
except EOFError:
    print("No user input detected. Using default ticker 'TCS.NS'.")
    ticker = 'TCS.NS'

# define cache file paths
MODEL_FILE = f'model_{ticker}.h5'
SCALER_FILE = f'scaler_{ticker}.joblib'
DATA_FILE = f'data_{ticker}.csv'


# checking for cached data
if os.path.exists(MODEL_FILE) and os.path.exists(SCALER_FILE) and os.path.exists(DATA_FILE):
    print(f"\nCached data and model for {ticker} found. Loading...")

    # Load cached data and scaler
    data_df = pd.read_csv(DATA_FILE)
    # Convert 'Close' and 'Volume' columns to numeric to prevent ValueError
    data_df['Close'] = pd.to_numeric(data_df['Close'], errors='coerce')
    data_df['Volume'] = pd.to_numeric(data_df['Volume'], errors='coerce')
    data = data_df[['Close']].values
    scaler = joblib.load(SCALER_FILE)

    # Load the pre-trained model
    model = load_model(MODEL_FILE)

    # Update data to get the very latest prices
    latest_df = yf.download(ticker, period="10d")
    if not latest_df.empty and pd.to_datetime(latest_df.index[-1]).date() != pd.to_datetime(data_df['Date'].iloc[-1]).date():
        print("New data available. Appending to existing dataset...")
        data_df = pd.concat([data_df, latest_df[['Close', 'Volume']].reset_index().rename(columns={'index': 'Date'})], ignore_index=True)
        data_df.drop_duplicates(subset=['Date'], keep='last', inplace=True)
        data = data_df[['Close']].values
        data_df.to_csv(DATA_FILE, index=False)


    scaled_data = scaler.fit_transform(data)

else:
    print(f"\nNo cached model for {ticker}. Downloading data and training new model...")

    try:
        df = yf.download(ticker, period="8y")
        if df.empty:
            raise ValueError("Could not download data for this ticker.")
        data = df[['Close']].values  # only closing prices for model
        df.reset_index().rename(columns={'index': 'Date'}).to_csv(DATA_FILE, index=False)
    except Exception as e:
        print(f"Error downloading data: {e}")
        print("Exiting program.")
        exit()

    #Scale data and create sequences
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)

    #Build and train LSTM model
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(60, 1)),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25, activation="relu"),
        Dense(1)
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")

#We need to define x and y before training
    seq_len = 60
    x, y = [], []
    for i in range(seq_len, len(scaled_data)):
        x.append(scaled_data[i - seq_len:i, 0])
        y.append(scaled_data[i, 0])
    x, y = np.array(x), np.array(y)
    x = np.reshape(x, (x.shape[0], x.shape[1], 1))

    split = int(0.8 * len(x))
    x_train, y_train = x[:split], y[:split]

    print("\nTraining Model...")
    model.fit(x_train, y_train, epochs=50, batch_size=32, verbose=1)

    #Save the trained model and scaler for future use
    model.save(MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)
    print("Model and scaler saved to disk for faster future predictions.")

# Create sequences from the loaded data for prediction
seq_len = 60
x, y = [], []
for i in range(seq_len, len(scaled_data)):
    x.append(scaled_data[i - seq_len:i, 0])
    y.append(scaled_data[i, 0])

x, y = np.array(x), np.array(y)
x = np.reshape(x, (x.shape[0], x.shape[1], 1))

# Train/Test split for plotting
split = int(0.8 * len(x))
x_test, y_test = x[split:], y[split:]

# Predictions
predictions = model.predict(x_test)
predictions = scaler.inverse_transform(predictions.reshape(-1, 1))  # back to price scale
y_test_rescaled = scaler.inverse_transform(y_test.reshape(-1, 1))

#Plotting Moving Averages
# Prepare full data for plotting MAs
data_full_df = pd.read_csv(DATA_FILE)
data_full_df['Close'] = pd.to_numeric(data_full_df['Close'], errors='coerce')
data_full_df['Date'] = pd.to_datetime(data_full_df['Date'])
data_full_df.set_index('Date', inplace=True)
data_full_df['MA100'] = data_full_df['Close'].rolling(window=100).mean()
data_full_df['MA200'] = data_full_df['Close'].rolling(window=200).mean()

# Plot 1: 100-Day Moving Average
plt.figure(figsize=(14, 6))
plt.plot(data_full_df['Close'], label='Actual Price', color='blue', alpha=0.5)
plt.plot(data_full_df['MA100'], label='100-Day Moving Average', color='orange')
plt.title(f"{ticker} 100-Day Moving Average")
plt.xlabel("Date")
plt.ylabel("Stock Price")
plt.legend()
plt.grid(True)
plt.show()

# Plot 2: 100-Day and 200-Day Moving Averages
plt.figure(figsize=(14, 6))
plt.plot(data_full_df['Close'], label='Actual Price', color='blue', alpha=0.5)
plt.plot(data_full_df['MA100'], label='100-Day Moving Average', color='orange')
plt.plot(data_full_df['MA200'], label='200-Day Moving Average', color='purple')
plt.title(f"{ticker} 100-Day and 200-Day Moving Averages")
plt.xlabel("Date")
plt.ylabel("Stock Price")
plt.legend()
plt.grid(True)
plt.show()

# Plotting the final prediction chart
plt.figure(figsize=(14,6))
plt.plot(y_test_rescaled, color="blue", label="Actual Stock Price")
plt.plot(predictions, color="red", label="Predicted Stock Price")
plt.title(f"{ticker} Stock Price Prediction")
plt.xlabel("Time")
plt.ylabel("Stock Price")
plt.legend()
plt.show()

# Calculate and display accuracy
# Calculate Mean Absolute Percentage Error (MAPE)
mape = mean_absolute_percentage_error(y_test_rescaled, predictions)
accuracy_percentage = (1 - mape) * 100

print(f"\nModel Accuracy: {accuracy_percentage:.2f}%")

# Final verdict and disclaimer

print("\nFinal Verdict:")
# Predict the next day's price to include it in the verdict
last_seq = scaled_data[-seq_len:]
last_seq = last_seq.reshape(1, seq_len, 1)
next_day_prediction_scaled = model.predict(last_seq)
next_day_prediction = scaler.inverse_transform(next_day_prediction_scaled)[0][0]
current_price = data_full_df['Close'].iloc[-1]

if next_day_prediction > current_price:
    verdict = "The model predicts an upward trend. This suggests potential for growth based on historical patterns."
else:
    verdict = "The model predicts a downward trend. This suggests potential for a decline based on historical patterns."

print(f"{verdict} The model's accuracy is {accuracy_percentage:.2f}%. It is essential to conduct further research before making any decisions. This output should not be considered as financial advice.")
