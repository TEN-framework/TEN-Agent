<h2>ASTRA Service</h2>

Now let's discuss what's under the hood. The ASTRA Service is composed of various ASTRA extensions, developed in different programming languages. These extensions are interconnected using Graph, which describes their relationships and illustrates the flow of data. Furthermore, sharing and downloading extensions are simplified through the ASTRA Extension Store and the ASTRA Package Manager.

<div align="center">

<image alt="ASTRA" src="./images/image.png">

</div>

<br>
<h2>ASTRA Extension</h2>

An extension is the fundamental unit of composition within the ASTRA framework. Developers can create extensions in various programming languages and combine them to build diverse scenarios and applications. ASTRA emphasizes cross-language collaboration, allowing extensions written in different languages to work together seamlessly within the same application or service.

For example, if an application requires real-time communication (RTC) features and advanced AI capabilities, a developer might choose to write RTC-related extensions in C++ for its performance advantages in processing audio and video data. Meanwhile, they could develop AI extensions in Python to leverage its extensive libraries and frameworks for data analysis and machine learning tasks.

#### Supported Languages

As of July 2024, we support extensions written in **C++**, **Golang** and **Python**.

<br>
<h2>Graph</h2>

A Graph in ASTRA describes the data flow between extensions, orchestrating their interactions. For example, the text output from a speech-to-text (STT) extension might be directed to a large language model (LLM) extension. Essentially, a Graph defines which extensions are involved and the direction of data flow between them. Developers can customize this flow, directing outputs from one extension, such as an STT, into another, like an LLM.

In ASTRA, there are four main types of data flow between extensions, they are **Command**, **Data**, **Image Frame** and **PCM Frame**.

By specifying the direction of these data types in the Graph, developers can enable mutual invocation and unidirectional data flow between plugins. This is especially useful for PCM and image data types, simplifying audio and video processing.

<br>
<h2>ASTRA Agent App</h2>

An ASTRA Agent App is a runnable server-side application that combines multiple Extensions following Graph rules to accomplish more sophisticated operations.An ASTRA Agent App is a robust, server-side application that executes complex operations by integrating multiple Extensions within a flexible framework defined by Graph rules. These Graph rules orchestrate the interplay between various Extensions, enabling the app to perform sophisticated tasks that go beyond the capabilities of individual components.

By leveraging this architecture, an ASTRA Agent App can seamlessly manage and coordinate different functionalities, ensuring that each Extension interacts harmoniously with others. This design allows developers to create powerful and scalable applications capable of handling intricate workflows and data processing requirements.

<br>
<h2> ASTRA Extension Store</h2>

The ASTRA Store is a centralized platform designed to foster collaboration and innovation among developers by providing a space where they can share their extensions. This allows developers to contribute to the community, showcase their work, and receive feedback from peers, enhancing the overall quality and functionality of the ASTRA ecosystem.

In addition to sharing their own extensions, developers can also access a wide array of extensions created by others. This extensive library of extensions makes it easier to find tools and functionalities that can be integrated into their own projects, accelerating development and promoting best practices within the community. The ASTRA Store thus serves as a valuable resource for both novice and experienced developers looking to expand their capabilities and leverage the collective expertise of the community.

<br>
<h2> ASTRA Package Manager</h2>

The ASTRA Package Manager streamlines the entire process of handling ASTRA extensions, making it easy to upload, share, download, and install them. It significantly simplifies the workflow by allowing extensions to specify their dependencies on other extensions and the environment. This ensures that all necessary components are automatically managed and installed, reducing the potential for errors and conflicts.

By automatically managing these dependencies, the ASTRA Package Manager makes the installation and release of extensions extremely convenient and intuitive. This tool not only saves time but also enhances the user experience by ensuring that every extension works seamlessly within the larger ecosystem. This level of automation and ease of use encourages the development and distribution of more robust and complex extensions, further enriching the ASTRA framework.