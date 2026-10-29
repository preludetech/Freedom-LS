We currently have a command called fls_dev/concrete/update_fls that gets run inside a concreate implementation of FLS. For example  /home/sheena/workspace/first_class/First-Class-LMS.git

This can be a frustrating expereince because if there are any integration issues then those need to be described in the concrete implementation and handed back to this repo to be fixed. Sometimes the concrete implementation ends up building a bunch of workarounds that need to get rolled back. It can be a confusing and error-prone and time consuming.

What I want to do instead:

1. Run the command from this repo
2. Maintain a list of paths to concrete implementations that need to be updated (paths on local machine)
3. Claude from here implements one spec at a time and runs tests and QA. The QA plan might need to be adapted.

If integration bugs are found, fix the problems here before continuing with integrating the next spec.
For small problems, just fix them. Otherwise make a new spec here to implement.

If a concrete implementation has implemented something that looks like it belongs in FLS (because it seems generally useful) then ask if it should be pulled in. Make specs as needed.
