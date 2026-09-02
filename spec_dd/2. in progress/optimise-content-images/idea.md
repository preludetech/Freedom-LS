freedom_ls/content_engine/management/commands/content_save.py

This command is used to save content to the database.  There are often images or pictures in the content. sometimes those are very big, for example 5 megabytes. That is not appropriate for how we use the images. We need to serve them to learners in our course player.  We either need to optimize images when we run content save. or we need to optimize the images when we serve them.
