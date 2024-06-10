---
title: Predict the Future with Prometheus
date: 2024-06-10 20:51
categories: [k8s, kubernetes, prometheus, alertmanager, promql]
tags: [kubernetes, k8s , prometheus, alertmanager, promql]     # TAG names should always be lowercase
---


![Tkubernetes is beautiful!](/assets/img/predict_cpu_usage.png "Prometheus-graph")

---

## Predict the Future with Prometheus

Predicting future trends and values is a crucial aspect of monitoring and alerting in any system. Prometheus, a powerful monitoring tool, provides functions that allow you to forecast future values based on current and historical data. One such function is `predict_linear`.

In this article, we'll explore how to use the `predict_linear` function in Prometheus to predict future trends. We'll cover the basics of the function and provide a few practical PromQL examples to help you get started.

### What is `predict_linear`?

The `predict_linear` function in Prometheus is used to predict the future value of a time series based on a linear regression of the current trend. This can be particularly useful for anticipating future load, capacity planning, or spotting potential issues before they become critical.

### Syntax

The basic syntax for the predict_linear function is as follows:

```bash
predict_linear(v range-vector, t scalar)
```
* v: The range vector over which to perform the linear regression.
* t: The amount of time into the future for which you want to predict the value.

### Practical Examples
Let's dive into a few examples to see how predict_linear can be used in real-world scenarios.

#### Example 1: Predicting CPU Usage
Suppose you want to predict the CPU usage of a server 10 minutes into the future. The following PromQL query will help you achieve this:

```bash
predict_linear(node_cpu_seconds_total{mode="user"}[5m], 600)
```
In this query:

*node_cpu_seconds_total{mode="user"}[5m]* selects the CPU usage in user mode over the past 5 minutes.
600 represents the number of seconds (10 minutes) into the future for which we want to predict the CPU usage.

#### Example 2: Forecasting Memory Usage
Predicting memory usage can help in capacity planning. Here’s how you can predict memory usage 30 minutes into the future:

```bash
predict_linear(node_memory_Active_bytes[10m], 1800)
```
In this query:

*node_memory_Active_bytes[10m]* selects the active memory usage over the past 10 minutes.
1800 represents the number of seconds (30 minutes) into the future for which we want to predict the memory usage.

#### Example 3: Estimating Network Traffic
Network traffic predictions can be essential for preventing bandwidth issues. Here’s an example of how to predict network traffic 15 minutes ahead:

```bash
predict_linear(node_network_receive_bytes_total[5m], 900)
```
In this query:

*node_network_receive_bytes_total[5m]* selects the total received network bytes over the past 5 minutes.
900 represents the number of seconds (15 minutes) into the future for which we want to predict the network traffic.

### Conclusion
The `predict_linear` function in Prometheus is a powerful tool for forecasting future values based on current trends. By using this function, you can gain valuable insights into your system's behavior and take proactive measures to ensure optimal performance.

Whether it's predicting CPU usage, memory usage, or network traffic, predict_linear can help you stay ahead of potential issues and make informed decisions about your infrastructure.

I hope this article has provided you with a clear understanding of how to use predict_linear in Prometheus. Try out these examples in your own environment and start predicting the future with confidence!
