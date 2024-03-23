---
title: How do write your own ansible plugin
date: 2023-11-09 16:10
categories: [ansible]
tags: [ansible, module, python]     # TAG names should always be lowercase
---

Eine triologie wie man ansible module schreibt, einmal lookup,inventory und modul.

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



