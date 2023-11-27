---
title: How do containers actually work
date: 2023-11-09 16:10
categories: [general]
tags: [general]     # TAG names should always be lowercase
---

wie funktionieren container eigentlich?
chroot + cgroups + namespaces
unterschied cd zu chroot (ändert nur den pointer im userspace)
beispiel in go ,wie man einen container schreibt

```go
func main() {
	switch os.Args[1] {
	case "run":
		runContainer()

	}
}

func runContainer() {
	cmd := exec.Command(os.Args[2], os.Args[3:]...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
```

```bash
go run main.go run /bin/bash
```

```c
chdir()
{
    chdirec(&u.u_cdir);
}

chroot()
{
    if (suser())
        chdirec(&u.u_rdir);
}
``````

```c
struct user
{
    ...
    struct inode *u_cdir;        /* pointer to inode of current directory */
    struct inode *u_rdir;        /* root directory of current process */
    ...
}
``````


So, a user on a Unix system has a current directory and root directory and chroot is a way to change the root value (u_rdir) in the same way cd changes the current working directory (u_cdir). In Unix V7 that’s basically all the chroot code I see, except for the syscall list and some userland code so that you can call chroot from your shell:
