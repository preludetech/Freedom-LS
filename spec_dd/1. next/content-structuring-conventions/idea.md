preferred directory structure:

Create a directory per content item. Eg instead of a file like `00. some-topic.md` make a directory like this:

```
00. some-topic/
    content.md
    images/  # whatever images there are for this item
    resources/ # any other resourced for this one
```

If an image or other resource is used by multiple content items or forms then it needs to be at a higher level eg:

```
images/
resources/  # used in multiple topics/forms
00. topic/
    images/ # images used only in topic one
01. some_form/
02. another_topic/
...
```

Similar for course parts. If an image is only used in a course part then keep it in the directory for that course part.
Apply this to all the demo content and adjust fls_content the plugin
