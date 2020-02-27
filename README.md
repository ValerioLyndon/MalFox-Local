# MalFox - Local Cover Database

### About

This branch of "MalFox" maintains a database on your local device of ID/Name/Cover Image relations, spanning the entirety of MAL's database. It does so by scraping the HTML and saving it to an SQLite database file.

Currently, this is used to generate various CSS preset files for use with peoples lists.

To build a complete database using the default delay, it takes more than a week of running nonstop. To save some time, you can find a version of the database I have built here: [Link](https://www.dropbox.com/s/lbcpk2qwv2y448y/covers.db)

### Info

Built using Python 3. Last confirmed working using Python 3.8.0.

Currently, all files are self-contained and are made to be launched from the file directory.

### Fair Warning

This program loads MyAnimeList's webpages directly and does not go through their API. This is because, at time of writing, no such API is publicly available.

Because of this, I cannot guarantee that using this program will not get you IP banned from MAL's services. That said, I have used it without issue for months, but things can change. If they see thousands of requests from a single IP running on a consistent timer, they may deem it unwanted.