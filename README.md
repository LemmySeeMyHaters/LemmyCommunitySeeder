# LemmyCommunitySeeder

LemmyCommunitySeeder is a bot inspired by [Fmstrat's LCS (Lemmy Community Seeder)](https://github.com/Fmstrat/lcs).
This bot is designed to crawl Lemmy instances and subscribe to their communities.
Unlike other lcs bots, this bot supports leverages concurrency to speed up the subscription process. 
This bot also allows you to fine-tune how much concurrency you want.
Although if you are not familiar with it, I suggest leaving it to default.

The goal of this bot can help you boost your instance content so users will have plenty of posts to browse through in their All feed.

## Usage

1. Clone the repository:
    ```shell
   git clone https://github.com/LemmySeeMyHaters/LemmyCommunitySeeder
   ```

2. Create and activate venv (recommended):
    ```shell
   cd LemmyCommunitySeeder 
   python -m venv venv
   ```
   On Mac/Linux:
   ```shell
   source venv/bin/activate
   ```
   On Windows:
   ```shell
   venv\Scripts\activate
   ```

3. Install Requirements:
   ```shell
   pip install -r requirements.txt
   ```

4. Create `.env` file:

   Create `.env` file which will contain your Lemmy Credentials.
   The file should look like this.
   The credentials from here will be used to run the bot.
   ```text
   LEMMY_USERNAME=<Username>
   LEMMY_PASSWORD=<Password>
   ```

5. Configure the `lcs_config.toml`:

   Configure the `lcs_config.toml` to your liking and make sure to edit the `local_instance_url`.
   All configs in `lcs_config.toml` are commented which explain what each config does.

6. Run the bot:

   Run the bot my running the main.
   ```shell
   python3 main.py
   ```

## Similar Projects

- [Lemmy Subscriber Bot (LSB)](https://github.com/lflare/lemmy-subscriber-bot)


