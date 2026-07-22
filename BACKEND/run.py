from invest import create_app

app = create_app()
# CORS is configured in create_app() — do NOT add it again here.
# Duplicate CORS calls override the whitelisted origins with wildcard `*`.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

