---
layout:     post
title:      "Dynamically Update Pod's Environment Variables"
subtitle:   "Technique to update a pod's environment variables based on changes to the referenced ConfigMap"
date:       2021-02-09 12:00:00
author:     "Akshay Elavia"
header-img: "img/post-bg-14.jpg"
---

<p>
It's a widely accepted practice to inject the environment variables into pods from ConfigMaps. This allows for more dynamic deployment of applications where the runtime properties need not be hardcoded into the application. Once the ConfigMap with the required key value pairs is created, all its entries can be used as environment variables for a pod. This can be configured as follows: 
<?prettify?> </p>
<pre class="prettyprint">
apiVersion: v1
kind: Pod
metadata:
  name: env-test-pod
  labels:
    app: env-test
spec:
  containers:
    - name: env-test-container
      image: itselavia/dynamic-update-env
      envFrom:
        - configMapRef:
            name: env-vars
</pre>
<p>
But, there are some use cases where the the environment variables needs to be modified and the application needs to react to those changes. This creates a bit of an operational issue because Kubernetes does not automatically restart the pod or updates its environment variables if a referenced ConfigMap is updated.</p>
<p>
However, Kubernetes does update the volume mounts of the pod if the ConfigMap is mounted to the pod. So the basic idea is alongwith setting the environment variables using envFrom and configMapRef, we also mount the ConfigMap to the pod at a specific directory. This is configured as follows: 
<?prettify?> </p>
<pre class="prettyprint">
apiVersion: v1
kind: Pod
metadata:
  name: env-test-pod
  labels:
    app: env-test
spec:
  containers:
    - name: env-test-container
      image: itselavia/dynamic-update-env
      envFrom:
        - configMapRef:
            name: env-vars
      volumeMounts:
        - mountPath: /config
          name: env-volume
  volumes:
    - name: env-volume
      configMap:
        name: env-vars
</pre>

<p>
We monitor the /config configuration directory for any changes. This example application uses <a href="https://github.com/fsnotify/fsnotify" target="_blank">fsnotify</a> which is a golang library which implements filesystem monitoring for many platforms. We also need to reprogram the application to monitor the configuration directory in the background and update the environment variables in the pod when any change event is received. The Go code snippet is shared below:
<?prettify?> </p>
<pre class="prettyprint">
func main() {

  watcher, err := fsnotify.NewWatcher()
  if err != nil {
    fmt.Println("cannot initialize Watcher ", err)
  }
  defer watcher.Close()

  // watcher will monitor the files in a background goroutine
  go func() {
    for {
      select {
      // reload the environment variables whenever changes are made in the /config directory
      case _, ok := <-watcher.Events:
        if !ok {
          return
        }
        reloadEnvVars()
      case err, ok := <-watcher.Errors:
        if !ok {
          fmt.Println("error from Watcher: ", err)
          return
        }
      }
    }
  }()

  // monitor the /config directory
  err = watcher.Add("/config/")
  if err != nil {
    fmt.Println("error adding directory to Watcher", err)
  }
}
</pre>
<p>
The overall steps are depicted in the below diagram. The source code is available at <a href="https://github.com/itselavia/dynamic-update-configmap-env-vars" target="_blank">this GitHub repository</a>
</p>
<a href="#">
    <img src="{{ site.baseurl }}/img/flow-diagram.png" alt="Flow Diagram for Dynamically Updating Environment Variables" style="display: block;margin-left: auto;margin-right: auto;">
</a>
<span class="caption text-muted">Flow Diagram for Dynamically Updating Environment Variables</span>