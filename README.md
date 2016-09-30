# CC-Server

Visit the [project website](http://www.curious-containers.cc/).

## Introduction
**Curious Containers** is an application management service that is able to execute thousands of short-lived applications in an distributed cluster environment by employing Docker Swarm.

In this context applications are atomic entities taking files and parameters as input and producing new files as output. They are short-lived in a sense that they calculate something and terminate as soon as all results have been produced.

Curious Containers supports scientific use cases like **biomedical analysis** and **reproducible research** by providing standardized methods for packaging applications and executing them in a compute environment. Therefore application dependencies are added to a compatible Docker container image, including all necessary scripts, binaries and configurations. [Read more...](http://www.curious-containers.cc/docs/html/introduction.html)
