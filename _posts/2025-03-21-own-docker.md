---
title: How to write your own Docker
date: 2025-03-31 20:30
categories: [k8s, kubernetes, docker, go]
tags: [k8s, kubernetes, docker, go]     # TAG names should always be lowercase
---


![Tkubernetes is beautiful!](/assets/img/own_docker.png "vpn-4-pennys-img")

---
## How to write your own Docker

Containers have revolutionized how we build and deploy applications, but have you ever wondered what lies underneath? In this article, we'll explore how to write your own simple container using Go. We'll demonstrate that at its core, a container is essentially a chroot environment combined with cgroups and namespaces, making it lightweight yet powerful.

## What is a container?

At its heart, a container isolates an application from its host system. This isolation is achieved using Linux namespaces and cgroups. The idea is simple: restrict the application to its own view of the filesystem, processes, and network. In essence, you're setting up a mini operating environment that runs a single process or application.

## Building a simple container in Go

The following Go code is a minimal example that mimics the behavior of a container runtime. It uses the Go standard library to execute a process within a controlled environment. Although the code is basic and omits advanced features like cgroups or sophisticated resource management, it gives you a clear picture of the underlying concept.

## The Code

Below is the prepared code snippet for our simple container:

```go
package main

import (
	"fmt"
	"os"
	"os/exec"
)

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
	cmd.Env = []string{"PS1=[d-container]# "}
	// adding linux namespaces (only works on linux, not osx)
	// cmd.SysProcAttr = &syscall.SysProcAttr{
	// 	Cloneflags: syscall.CLONE_NEWUTS | syscall.CLONE_NEWPID | syscall.CLONE_NEWNS,
	// }

	if err := cmd.Run(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
```

## How It Works

### Command Line Arguments:
The program expects a command-line argument. When run with run, it calls the runContainer function to start the containerized process.

#### Executing the Container:
The runContainer function uses exec.Command to start a new process. Standard input, output, and error are attached to allow interactive usage. Additionally, the environment variable PS1 is set to mimic a shell prompt inside the container.
#### Namespaces and Isolation:
Although commented out in the snippet, Linux namespaces (using syscall.SysProcAttr) can be enabled. Namespaces provide isolation for the container by creating separate instances of the host's global resources. By using flags like CLONE_NEWUTS, CLONE_NEWPID, and CLONE_NEWNS, the process gets its own hostname, process IDs, and filesystem namespace, respectively. This is what fundamentally separates a container from a regular process.

### Chroot and Groups:
In more advanced implementations, you might also use chroot to change the apparent root directory for the process, further isolating the filesystem. Additionally, setting group IDs can help in managing user permissions within the container environment. Our simple example does not cover these in detail, but they are the building blocks of container security and isolation.

## Why Build Your Own Docker?

Writing your own container from scratch is an excellent exercise for understanding how containers work under the hood. It demystifies the abstraction layers provided by container engines like Docker and offers insights into how namespaces, cgroups, and chroot environments contribute to process isolation.

While production container runtimes are highly optimized and include many more features, this simple example provides a solid foundation for grasping the basic concepts.

## Conclusion

Containers are not magic; they're built on well-understood Linux features that provide process isolation and resource management. By experimenting with your own container runtime in Go, you can gain a deeper understanding of these underlying technologies and appreciate the elegance of containerization.

Feel free to expand on this example, add more features like cgroup management, or integrate proper error handling and security practices to build a more robust solution.

Happy coding, and enjoy your journey into containerization!