import toml

# Load configuration from config.toml
config = toml.load("config.toml")

if __name__ == "__main__":
    print("Configuration Loaded:", config)
