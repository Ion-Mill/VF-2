SPDX-FileCopyrightText: Copyright (C) 2026 OPC Foundation, Inc.
SPDX-License-Identifier: LicenseRef-OPC-Specification-1.15
License: https://opcfoundation.org/license/specifications/1.15/

OPC-10030: OPC Unified Architecture - Common Object Model: ISA-95
Version: 1.00
Published: 2013-11-06

1 Scope

This standard is an extension of the overall OPC Unified Architecture standards and defines an information model that conforms to the Common Object Models defined in ANSI/ISA-95.00.02-2010 Enterprise/Control System Integration - Part 2: Object Model Attributes standard, referred to as ISA-95 in this document. The Common Object Models describe the object model for Personnel Information, Role Base Equipment Information, Physical Asset Information, and Material Information as resources for manufacturing operations and controls, and is widely used in many industries for information exchange in Manufacturing Operations Management (MOM) systems. The international version of this ISA-95 standard is IEC 62264-2:2013, the Common Object Models in both are the same.

The Business To Manufacturing Markup Language (B2MML) is an open source XML implementation of the ISA-95 and IEC 62264 standards.  The Business To Manufacturing Markup Language (B2MML) is used courtesy of the Manufacturing Enterprise Solutions Association (MESA International). B2MML is used as the de facto standard interface to exchange the contents defined in ISA-95. The OPC UA implementation will complement the existing B2MML implementations by providing a secure and reliable environment that is widely accepted in the manufacturing industries.

The modelling targets of this standard shall exist in an OPC UA Address Space. This standard does not consider the modelling targets that are identified in other standards or vendor specifications.

2 Normative References

The following referenced documents are indispensable for the application of this standard. For dated references, only the edition cited applies. For undated references, the latest edition of the referenced document (including any amendments) applies.

OPC 10000-1, OPC Unified Architecture - Part 1: Overview and Concepts

OPC 10000-2, OPC Unified Architecture - Part 2: Security Model

OPC 10000-3, OPC Unified Architecture - Part 3: Address Space Model

OPC 10000-4, OPC Unified Architecture - Part 4: Services

OPC 10000-5, OPC Unified Architecture - Part 5: Information Model

OPC 10000-6, OPC Unified Architecture - Part 6: Mappings

OPC 10000-7, OPC Unified Architecture - Part 7: Profiles

OPC 10000-8, OPC Unified Architecture - Part 8: Data Access

OPC 10000-9, OPC Unified Architecture - Part 9: Alarms and Conditions

OPC 10000-10, OPC UA Specification: Part 10 - Programs

OPC 10000-11, OPC Unified Architecture - Part 11: Historical Access

OPC 10000-12, OPC Unified Architecture - Part 12: Discovery and Global Services

OPC 10000-13, OPC Unified Architecture - Part 13: Aggregates

ISA-95 Part1:	ANSI/ISA-95.00.01-2010 Enterprise-Control System Integration - Part1 Models and Terminology

ISA-95 Part2:	ANSI/ISA-95.00.02-2010 Enterprise-Control System Integration - Part2 Object Model Attributes

B2MML-Common: Business To Manufacturing Markup Language B2MML - Common Version 0600 https://services.mesa.org/resourcelibrary/showresource/03181327-8375-44b7-b42a-07ac3dba2119

B2MML-Personnel: Business To Manufacturing Markup Language B2MML - Personnel Version 0600 https://services.mesa.org/resourcelibrary/showresource/03181327-8375-44b7-b42a-07ac3dba2119

B2MML-Equipment: Business To Manufacturing Markup Language B2MML - Equipment Version 0600 https://services.mesa.org/resourcelibrary/showresource/03181327-8375-44b7-b42a-07ac3dba2119

B2MML-PhysicalAsset	: Business To Manufacturing Markup Language B2MML - Physical Asset Version 0600 https://services.mesa.org/resourcelibrary/showresource/03181327-8375-44b7-b42a-07ac3dba2119

B2MML-Material: Business To Manufacturing Markup Language B2MML - Material Version 0600 https://services.mesa.org/resourcelibrary/showresource/03181327-8375-44b7-b42a-07ac3dba2119

CCTS:	UN/CEFACT Core Components Data Type Catalogue Version 3.1

XMLSchema Part2: W3C XML Schema Definition Language (XSD) 1.1 Part 2: Datatypes

ISO 4217: Codes for the representation of currencies and funds

ISO 8601-2004: Data elements and interchange formats

UN/ECE: UN/CEFACT UN/ECE Recommendation No.20 - Codes for Units of Measure Used in International Trade

IETF RFC2045: Multipurpose Internet Mail Extensions (MIME) Part One

IETF RFC2046: Multipurpose Internet Mail Extensions (MIME) Part Two

IETF RFC2047: Multipurpose Internet Mail Extensions (MIME) Part Three

Annex15: Unicode Standard Annex #15: Unicode Normalization Forms

3 Terms, definitions and conventions

3.1 Overview

It is assumed that basic concepts of OPC UA information modelling are understood in this specification. This specification will use these concepts to describe the ISA-95 Common Object Models.  The concepts and terms used to describe the OPC UA Information models are defined in other parts and listed in the following sections. Note that OPC UA terms and terms defined in this standard are italicized.

For the purposes of this document, the terms and definitions given in OPC 10000-1, OPC 10000-3, OPC 10000-8, and OPC 10000-9 as well as the following apply.

3.2 OPC UA ISA-95 Terms

3.2.1 ISA95<Term>

3.2.1.1 General

This standard adopts adding an ISA95 prefix to all ISA-95 defined terms that are used in this standard that are also defined by OPC. The <Term> is the terminology defined by ISA-95. This allows the terminology used in ISA-95 to be easily distinguished from terminology defined in OPC UA.

3.2.1.2 ISA95Class

a concept that categorizes a modelling target defined as a Class in ISA-95 Part2.

Note: It is different than the concept of a Type defined in OPC UA OPC 10000-3, even though the OPC UA Type is also a concept to classify a modelling target and it is similar to a concept of class used in OOAD.

3.2.1.3 ISA95Object

a concept that represents Equipment, Personnel, Physical Assets, and Material defined in ISA-95.

3.2.1.4 ISA95Property

a concept that represents characteristics of a modelling target defined as a Property in ISA-95 Part2.

Note: The semantic of the ISA95Property is similar to Property defined in OPC UA, but the model structure is different since an ISA95Property may have a Reference to an ISA95TestSpecification and an ISA95TestResult and such References are not allowed in an OPC UA Property. An ISA95Property more closely matches an OPC UA Variable, which is allowed to have children.

3.2.1.5 ISA95Attribute

a concept that represents an attribute of a modelling target defined as attribute in ISA-95. 

Note: It is different from a concept of Attribute defined in OPC UA, where Attribute is a concept to represent information of a NodeClass. ISA95Attribute is represented as VariableType in this standard.

3.2.2 UML<Term>

3.2.2.1 General

UML<Term> is a terminology defined in UML. In this standard, terminologies used in UML are described in this format to distinguish terminology defined in OPC UA and ISA-95.

3.3 Abbreviations and symbols

DA,Data Access
AC,Alarm and Condition
HA,Historical access
CCTS,Core Components Technical Specification (building blocks for data modelling)
CDT,Core Data Types
ERP,Enterprise Resource Planning
EAM,Enterprise Asset Management
LIMS,Laboratory Information Management Systems
MES,Manufacturing Execution Systems
CMMS,Computerized Maintenance Management Systems
MOM,Manufacturing Operations Management
SCADA,Supervisory Control and Data Acquisition
WMS,Warehouse Management Systems
PLC,Programmable Logic Controllers
DCS,Distributed Control Systems
OCS,Open Control Systems

3.4 OPC UA Notation

This standard uses ModellingRule that are OptionalPlaceholder and MandatoryPlaceholder to define instance declarations, and defines a rule that the BrowseName of instance declarations having an OptionalPlaceholder or MandatoryPlaceholder ModellingRule be enclosed in angle brackets (<>). Originally, this rule is defined in OPC 10000-3 as a recommendation. This naming rule is also used in the description of a table. The BrowseName of a Node that has OptionalPlaceholder or MandatoryPlaceholder ModellingRule are described with angle brackets, which denotes that the name is not fixed. For example BrowseName of Property is described as <PropertyName> in graphical notation and tables results in a Property that can have any name.

4 Concept

4.1 Overview

Automation does not end with equipment control; it also includes higher levels of control that manage personnel, equipment, and materials across production areas. Effectiveness in manufacturing companies is not based solely on equipment control capability. The ISA-95 Enterprise/Control System Integration standard defines 5 levels of activities in a manufacturing organization. Generally, automation and control support Levels 1 and 2, Manufacturing Operations Management (MOM) systems support Level 3, and business Enterprise Resource Planning (ERP) systems support Level 4 activities. ISA-95 defines four primary types of information that often must be exchanged among MOM systems and between ERP systems and MOM systems, these types are; 

Information about material and the properties of materials, 

Information about equipment as it pertains to the operations being performed, 

Information about the physical assets that make up the equipment, 

Information about personnel and their roles and qualifications.

ISA-95 provides a standard manner to uniquely describe this information for exchange, including the interrelationships between the various types of information. The ISA-95 standard is described in multiple parts, where each part describes a portion of the standard. The 2010 versions of Parts 1 and 2 of the ISA-95 standard have been used to define a UA companion standard using OPC UA constructs for the purpose of exposing the ISA-95 objects and attributes in an OPC UA environment. This first release of the UA companion standard supports a subset of the entire ISA-95 standard, covering the role based equipment, physical asset, material and personnel object models in ISA-95 (see Figure 1). Later revisions of the companion standard may include support for the other ISA-95 object models such as process segment, operations definition, operations schedule, operations performance and operations capability object models. 

[Figure: Figure 1 - ISA-95 Overview]

4.2 ISA-95 Summary

4.2.1 Introduction

For an OPC UA user that may not be familiar with ISA-95, the following section provides a brief overview of key features that ISA-95 provides along with a little background related to ISA-95 and the concepts behind it.

4.2.2 Why ISA-95?

Typically in a manufacturing world plants optimize their control systems to maximize production and profits. Manufacturing companies must also be efficient at coordinating and controlling personnel, materials, and equipment across different control systems in order to reach their maximum potential. This coordination and control must occur in at least four different parts of an organization; production, quality tests and test labs, warehousing and inventory management, and maintenance. 

This coordination and control is often supported by Manufacturing Execution Systems (MES) for ma­nagement of production operations, Laboratory Information Management Systems (LIMS) for quality tests and test lab management, Warehouse Management Systems (WMS) or Tank Farm Management systems for management of inventory operations, and Asset Management or Computerized Maintenance Management Systems (CMMS) for maintenance operations. These systems together are collectively called Manufacturing Operations Management (MOM) systems. MOM defines a diverse set of functions that operate above automation control systems, reside below the level of enterprise business systems and are local to a site or area.

ISA-95 was created to allow efficient sharing and coordination of information between the various levels. The following subsections summarize the information that needs to be exchanged. 


            Sharing Material Information: Manufacturing requires materials. It is not surprising that manufacturing systems have a requirement to identify and track materials because the main purpose of manufacturing is to convert materials in one form into materials of another form. An important part of MOM integration is maintaining and exchanging material identification and information. 

MES identify materials and their suitability for use, batch management systems confirm that the correct materials are used as specified in the recipes, 

Tracking and tracing systems (bar-code scanners and RFID readers),

LIMS confirm that the correct materials are tested and the correct materials are used in testing, 

WMS identify materials in their storage locations. 

Shared material information can be divided into three main categories;

material class information identifies the materials without regard to the source of the material, 

material definition information identifies material from specific vendors or sources, 

material lot information identifies actual material, its location and quantity. 


            Sharing Equipment Information: One important element of managed information is the correct identification of the equipment used for manufacturing. Equipment identification is used for: 

scheduling,

tracking and tracing, 

maintenance, 

troubleshooting, 

visualization (HMI), 

capacity tracking, 

OEE (Overall Equipment Effectiveness) calculations.

 Unfortunately, it is not uncommon for a manufacturing company to have multiple identifications for a single piece of equipment. Therefore, a critical aspect of equipment information management is managing different equipment ID's across multiple vendor systems and applications. 


            Sharing Physical Asset Information: Identification of a unique physical asset, irrespective of the role the equipment is performing is vital for:

maintenance,

equipment qualification and regulatory compliance, 

financial asset tracking 

While equipment is typically identified by a tag, such as TT-101 for a temperature transmitter, that identifies the role, or current function, of a specific asset physical asset information this is not sufficient for tracking individual assets for maintenance and financial purposes.  To manage assets a company must have a unique identifier for the physical asset that is independent of the role it serves at a specific point in time.  For example temperature transmitter TT-101 may have a serial number of X2 on a specific day, the next day the transmitter may be swapped out with a replacement transmitter with the same specifications but with the serial number X3.  X3 would then be configured to have the tag TT-101 and X2 would no longer be known as TT-101.  In order to track the transmitters X2 and X3 the physical asset information model would be used, while for operations purposes it is only important that TT-101 is in use and providing a temperature reading, the operators and control systems do not generally need to know the asset tag of TT-101, they just need the tag.

Tracking of individual physical assets allows companies to monitor individual asset's health records, ensure they are qualified for production and track them in financial systems.


            Sharing Personnel Information: Multiple regulatory rules, laws, and internal procedures require that personnel who perform shop floor actions are unequivocally identified, are authorized to perform the actions, and have valid training or qualifications to perform the actions. Because personnel information is usually maintained in multiple IT systems and control systems, it is a key area of exchanged information. Specific uses in different systems that require coordination and sharing include: 

MES Personnel qualification to be checked before someone is allowed to take an action 

LIMS Identification of approved personnel to perform tests and handle materials, often based on their training qualifications, 

AM Certification information about personnel performing maintenance activities to ensure that they have the proper training required by the activity, 

WMS Certification that personnel are trained and qualified to handle material movement systems, such as fork trucks or crane systems. 

4.2.3 ISA-95

The ISA-95 Enterprise/Control System Integration standard defines five levels of activities in a manufacturing organization. Generally, automation and control support Levels 1 and 2, MOM systems support Level 3, and business Enterprise Resource Planning (ERP) systems support Level 4 activities. The ISA-95 levels are shown in Figure 1.


            Level 0 defines the actual physical processes.


            Level 1 elements are the sensors and actuators attached to the control functions in automation systems. 


            Level 2 automation and control systems have real-time responses measured in sub-seconds and are typically implemented on Programmable Logic Controllers (PLC), Distributed Control Systems (DCS), and Open Control Systems (OCS).


            Level 3 typically operates on time frames of days, shifts, hours, minutes, and seconds. Level 3 functions also include maintenance functions, quality assurance and laboratory functions, and inventory movement functions, and are collectively called Manufacturing Operations Management. A wide variety of systems support the activities, including SCADA (Supervisory Control and Data Acquisition) systems for monitoring the process and providing operator control, batch control systems for execution of recipes, data historians for the collection and preservation of time based data from Level 2 systems, recipe and document management systems for managing recipes and workflow instructions, detailed scheduling, campaign management or work dispatching, and work or product tracking. 


            Level 4 typically operates on time frames of months, weeks, and days. Enterprise Resource Planning (ERP) logistics systems are used to automate Level 4 functions. Level 4 is called Business Planning and Logistics.

[Figure: Figure 2 - Five Activity Levels in Business]

It is important to remember that each level has some form of control and each level has its own definition for real-time. Level 3 systems consider real-time to mean information available a few seconds after shop floor events occur. Level 4 systems consider real-time to mean that logistics and material information is available daily or within a few hours after the end of a shift. 

ISA-95 typically deals with information exchange across Level 3 systems or between Level 3 and Level 4 systems. Specifically this would involve information exchange between ERP, EAM, CMMS, MES, WMS, LIMS, PLC and DCS systems. This information exchange in real-time is often required in order to allow workflows and recipes to execute in a timely manner. ISA-95 defines four primary types of information that often must be exchanged among MOM systems and between ERP systems and MOM systems, these types are; information about material and the properties of materials, information about equipment as it pertains to the operations being performed, information about the physical assets that make up the equipment, and information about personnel and their roles and qualifications. 

4.2.4 Modelling Approach of ISA-95

The ISA-95 modelling approach to information is based on a "Property" model. [Note this is an ISA Property not a Property as defined by OPC UA] The ISA-95 models define a minimum set of industry-independent information as attributes. Industry specific, application specific, and company specific information are represented as property objects. For example, the personnel class property would be used to define application or industry specific attributes for personnel classes, and person property would be used to contain instance values for the properties. 

In the ISA-95 resource models there are "Classes" and "Instances". The word "Class" used as part of an object definition name should be considered as a classification, not as a "Class" in the official UML Modelling definition. For example: "Personnel Class" should be considered a "Personnel Classification", because it is used to distinguish between the kinds of personnel in the real world and to define properties that would be common to personnel within the same classification. The UML description of each of the ISA Information models is described. The ISA-95 Model also includes definitions of common attributes. These definitions are not part of the UML figures, but are included as text in the ISA-95 specification.


            
              Material:
              is from ISA-95.00.02, it is the ISA-95 material object model.  This is the definition of the lots, sublots, material definitions, and material classes involved in production. This information allows Level 3 and Level 4 systems to unambiguously identify material specified in production schedules and consumed or produced in actual production.  A prime business driver for using the material model is to provide the ability to trace all materials used in the manufacture of a product to aide in quality analysis and product recalls.

Each Material Definition instance defines a type of material, such as Acetic Acid, grade 4.  Each Material Definition may have specific properties, such as pH. These properties can be nested, in that a property can have its own properties. Material Definitions may be assembled from other Material Definitions, as in the case of a sub-assembly in car manufacturing, such as a transaxle which is identified as a Material Definition but is pre-assembled from multiple other Material Definitions.  The sub-assembly record keeping is important to maintain traceability. 

Material Definitions may belong to a Material Class. Material Classes are used as logical groups to manage Material definitions. Material Classes also have properties that can be nested and may also use the same assembly construct as used by Material Definitions.

Each Material Lot is an instance of a Material Definition that is uniquely identified. Material Lots also have properties that can be nested and may also use an assembly construct similar to that used by Material Definitions, the difference is that a Material Lot may be assembled from other Material Lots and/or Material Sublots. Material Lot instance properties are typically used to track specific shipments or orders of material.

Each Material Sublot is an instance of a Material Definition that is uniquely identified. Material Sublots do not have properties since each sublot instance must have the same properties as the Material Lot it is part of. Material Sublots may also use the same assembly construct as used by Material Lots. Material Sublot instances are typically used to provide tracking resolution within Material Lots, for example a Material Lot may have been received from a vendor in ten barrels, each barrel may be identified as a separate Material Sublot in order to track its movements and environmental conditions during storage and production.

The Material Test Specification identifies a test that may be associated with determining the value for a property of a Material Class, Material Definition or Material Lot instance. The information obtained from running the test can be modelled in the QA Test Result.

[Figure: Figure 3 - Material Model]


            Personnel: Figure 2 is from ISA-95.00.02, it is the ISA-95 personnel object model. This is the definition of the persons and personnel classes (roles) involved in production. This information may be used to associate production with specific persons as part of a production record, or with personnel classes to allocate production costs. 

Each instance of the Personnel Class from ANSI/ISA-95.00.02, is the Personnel object model. Each instance of the Personnel Class defines a role that a person can perform, such as a Draftsman. Each role may have specific properties, such as a Drafting License Number and a License Expiration Date. These Properties can also have their own nested properties. Each Person can be associated to one or more Personnel Class Roles. If the person is a Draftsman, then the Person Properties define the values for the Drafting License Number and License Expiration Date for that person. The Qualification Test Specification identifies a test that may be associated with determining the value for a property (such as a test for Draftsman used to obtain a Drafting License Number.) The information obtained from taking the test can be modelled in the Qualification Test Result. 

[Figure: Figure 4 - Personnel Model]

This modelling approach for ISA-95 means that properties must be able to be dynamically queried and browsed. The properties available for individual objects will be different, for example in Figure 22 - Personnel Overview, Joe Smith has a Drafting License Number, but Sally Jones does not.  


            Equipment: Figure 5 is, from ISA-95.00.02, it is the equipment object model.  This is the definition of the roles that equipment and equipment classes perform in production, inventory management, and quality test labs. This information may be used to associate production with specific equipment as part of a production record, or with equipment classes to schedule production and allocate costs

 Each instance of the Equipment Class defines a classification of equipment, such as a tank. Each Equipment Class may have specific properties, such as a volume. These properties can be nested, in that a property can have its own properties. Each piece of Equipment can be associated to one or more Equipment Classes. If the Equipment is a tank, then the Equipment Properties define the values for the volume of the tank. Equipment can also be nested, in that they can contain other Equipment.  The tank may also include several sensors such as temperature. The modeller can choose between extra properties or next properties and nest equipment depending on their own criteria. The Equipment Capability Test Specification identifies a test that may be associated with determining the value for a property. The information obtained from running the test can be modelled in the Equipment Capability Test Result.

[Figure: Figure 5- Equipment Model]

The Modelling approach for ISA-95 results in multiple levels of Equipment and Equipment Classes.  By definition if an Equipment is defined by an Equipment Class then it will have Equipment Properties that correspond to the Equipment Class Properties in the defining Equipment Class.


            Physical Assets: 
            Figure 6 is from ISA-95.00.02, it is the physical asset object model. This is an identification of the specific physical asset (by serial number or asset ID) used in manufacturing operations. It also includes the make and model information that identifies the type of physical asset and its properties. 

 Each instance of the Physical Asset Class defines a classification of Physical Asset, such as a valve. Each class may have specific properties, such as a percent open. These properties can be nested, in that a property can have its own properties. Each Physical Asset is associated to one Physical Asset Classes. This relationship is more like a type of, for example a car would be a Porsche 911 Carrera S, and it could not also be any other model. If the Physical Asset is a car, then the Physical Asset Properties define the values for the colour of the car and maybe the option package associated with the car. The option package would have its own properties such as leather interior, sun roof etc.. Physical Assets can also be nested, in that they can contain other Physical Assets.  For example a Car would contain four tires that have their own Physical Asset Class. The Physical Asset Capability Test Specification identifies a test that may be associated with determining the value for a property. The information obtained from running the test can be modelled in the Physical Asset Capability Test Result.

[Figure: Figure 6 - Physical Asset Model]

The Modelling approach for ISA-95 results in multiple levels of Physical Assets.  By definition if a Physical Asset is defined by a Physical Asset Class then it will have Physical Asset Properties that correspond to the Physical Asset Class Properties in the defining Physical Asset Class.

4.2.5 Key Points

ISA-95 is an abstract specification in that it does not provide any implementation. Other organizations, such as MESA, have created an implementation (B2MML) of the ISA-95 standard. B2MML generated a mapping of the ISA-95 standard that is appropriate for the technology used in the mapping, but the mapping used does not in all cases map well to OPC UA. This specification generates a mapping based on the ISA-95 specification, and where possible it follows the B2MML mapping to allow an easier translation of a B2MML model to an OPC UA Model.

The ISA-95 Model also expects end users to generate a custom model that is based on the defined constructs. The resulting model contains a large amount of information and can require considerable time to develop. The ability to translate a B2MML model to an OPC UA model is an attempt to allow reuse of the extended effort to define a B2MML model. 

4.3 OPC UA Summary

4.3.1 Introduction

For ISA-95 user that may not be familiar with OPC UA the following section provides a brief overview of key features that OPC UA provides.

4.3.2 What is OPC UA?

OPC UA is an open and royalty free set of standards designed as a universal communications protocol. While there are numerous communication solutions available, OPC UA has several advantages:

A state of art security model (see OPC 10000-2).

A fault tolerant communication protocol.

An information modelling framework that allows application developers to represent their data in a way that makes sense to them.

OPC UA has a broad scope which delivers for economies of scale for application developers. This means that a larger number of high quality applications at a reasonable cost are available. When combined with powerful semantic models such as ISA-95, OPC UA makes it easier for end users to access data via generic commercial application.

The OPC UA model is scalable from small devices to ERP systems. OPC UA devices process information locally and then provide that data in a consistent format to any application requesting data - ERP, MES, PMS, Maintenance Systems, HMI, Smartphone  or a standard Browser, for examples. For a more complete overview see OPC 10000-1.

4.3.3 Basics of OPC UA

As an Open Standard, OPC UA is based on standard Internet technologies - TCP/IP, HTTP, Ethernet, and XML.

As an Extensible Standard, OPC UA provides a set of services (see OPC 10000-4) and a basic information model framework. This framework provides an easy manner for creating and exposing vendor defined information in a standard way. More importantly all OPC UA Clients are expected to be able to discover and use vendor defined information. This means OPC UA users can benefit from the economies of scale that come with generic visualization and historian applications. This specification is an example of an OPC UA Information Model designed to meet the needs of developers and users.

OPC UA Clients can be any consumer of data from another device on the network to browser based thin clients and ERP systems. The full scope of OPC UA applications are shown in Figure 7.

[Figure: Figure 7 - The Scope of OPC UA within an Enterprise ]

OPC UA provides a robust and reliable communication infrastructure having mechanisms for handling lost messages, failover, heartbeat, etc. With its binary encoded data it offers a high-performing data exchange solution. Security is built into OPC UA as security requirements become more and more important especially since environments are connected to the office network or the internet and attackers are starting to focus on automation systems

4.3.4 Information Modelling in OPC UA

4.3.4.1 Concepts

OPC UA provides a framework that can be used to represent complex information as Objects in an address space which can be accessed with standard web services. These Objects consist of Nodes connected by References. Different classes of Nodes convey different semantics. For example a Variable Node represents a value that can be read or written. The Variable Node has an associated DataType that can define the actual value, such as a string, float, structure etc. It can also describe the variable value as a variant. A Method Node represents a function that can be called. Every Node has a number of Attributes including a unique identifier called a NodeId and non-localized name called as BrowseName. An Object representing a 'Reservation' is shown in Figure 8.

[Figure: Figure 8 - A Basic Object in an OPC UA Address Space ]

Object and Variable Nodes are called Instance Nodes and they always reference a Type Definition (ObjectType or VariableType) Node which describes their semantics and structure. Figure 9 illustrates the relationship between an Instance and its Type Definition.

The Type Nodes are templates that define all of the children that can be present in an Instance of the Type. In the example in Figure 9 the PersonType ObjectType defines two children: First Name and Last Name. All instances of PersonType are expected to have the same children with the same BrowseNames. Within a Type the BrowseNames uniquely identify the child. This means Client applications can be designed to search for children based on the BrowseNames from the Type instead of NodeIds. This eliminates the need for manual reconfiguration of systems if a Client uses Types that multiple devices implement.

OPC UA also supports the concept of sub typing. This allows a modeller to take an existing Type and extend it. There are rules regarding sub typing defined in OPC 10000-3, but in general they allow the extension of a given type or the restriction of a DataType. For example the modeller may decide that the existing ObjectType in some cases needs an additional variable. The modeller can create a Subtype of the object and add the variable. A client that is expecting the parent type can treat the new Type as if it was of the parent Type. With regard to DataTypes, if a variable is defined to have a numeric value, a sub type could restrict the Value to a float.

[Figure: Figure 9 - The Relationship between Type Definitions and Instances ]

References allow Nodes to be connected together in ways that describe their relationships. All References have a ReferenceType that specifies the semantics of the relationship. References can be hierarchical or non-hierarchical. Hierarchical references are used to create the structure of Objects and Variables. Non-hierarchical are used to create arbitrary associations. Applications can define their own ReferenceType by creating Subtypes of the existing ReferenceType. Subtypes inherit the semantics of the parent but may add additional restrictions. Figure 10 depicts several references connecting different Objects.

[Figure: Figure 10 - Examples of References between Objects ]

The figures above use a notation that was developed for the OPC UA specification. The notation is summarized in Figure 11. UML representations can also be used; however, the OPC UA notation is less ambiguous because there is a direct mapping from the elements in the figures to Nodes in the address space of an OPC UA server.

[Figure: Figure 11 - The OPC UA Information Model Notation]

A complete description of the different types of Nodes and References can be found in OPC 10000-3 and the base OPC UA Address space is described in OPC 10000-5.

OPC UA specification defines a very wide range of functionality in its basic information model. It is not expected that all Clients or Servers support all functionality in the OPC UA specifications. OPC UA includes the concept of profiles, which segment the functionality into testable certifiable units. This allows the development of companion specification (such as OPC UA for ISA-95) that can describe the subset of functionality that is expected to be implemented. The profiles do not restrict functionality, but generate requirements for a minimum set of functionality (see OPC 10000-7)

The OPC Foundation also defines a set of information models that provide a basic set of functionality. The Data Access specification (see OPC 10000-8) provides a basic information model for typical data. The Alarm and Condition specification (see OPC 10000-9) defines a standard information model for Alarms and Conditions.  The Programs specification (see OPC 10000-10) defines a standard information model for extending the functionality available via method calls and state machines. The Historical Access specification (see OPC 10000-11) defines the information model associated with Historical Data and Historical Events. The aggregates specification (see OPC 10000-13) defines a series of standard aggregate functions that allow a Client to request summary data. Examples of aggregates include averages, minimums, time in state, Standard deviation, etc.

4.3.4.2 Namespaces

OPC UA allows information from many different sources to be combined into a single coherent address space. Namespaces are used to make this possible by eliminating naming and id conflicts between information from different sources. Namespaces in OPC UA have a globally unique string called a NamespaceUri and a locally unique integer called a NamespaceIndex. The NamespaceIndex is only unique within the context of a Session between an OPC UA Client and an OPC UA Server. All of the web services defined for OPC UA use the NamespaceIndex to specify the Namespace for qualified values.

There are two types of values in OPC UA that are qualified with Namespaces: NodeIds and QualifiedNames. NodeIds are globally unique identifiers for Nodes. This means the same Node with the same NodeId can appear in many Servers. This, in turn, means Clients can have built in knowledge of some Nodes. OPC UA Information Models generally define globally unique NodeIds for the TypeDefinitions defined by the Information Model.

QualifiedNames are non-localized names qualified with a Namespace. They are used for the BrowseNames of Nodes and allow the same Names to be used by different information models without conflict. The BrowseName is used to identify the children within a TypeDefinitions. Instances of a TypeDefinition are expected to have children with the same BrowseNames. TypeDefinitions are not allowed to have children with duplicate BrowseNames; however, Instances do not have that restriction.

4.3.4.3 Companion Specifications

An OPC UA companion specification for an industry specific vertical market describes an information model by defining ObjectTypes, VariableTypes, DataTypes and ReferenceTypes that represent the concepts used in the vertical market. Table 1 contains an example of an ObjectType definition.

Table 1 - Example ObjectType Definition
Attribute,Value
BrowseName,WidgetType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseObjectType from OPC 10000-5.
,,,
HasProperty,Variable,Color,String,PropertyType,Mandatory
HasProperty,Variable,Flavor,LocalizedText,PropertyType,Mandatory
HasProperty,Variable,Rank,Int32,PropertyType,Mandatory

The BrowseName is a non-localized name for an ObjectType. 

IsAbstract is a flag indicating whether instances of the ObjectType can be created.

The bottom of the table lists the child nodes for the type. The Reference is the type of reference between the Object instance and the child Node. The NodeClass is the class of Node. The BrowseName is the non-localized name for the child. The DataType is the structure of the Value accessible via the Node (only used for Variable NodeClass Nodes) and the TypeDefinition is the ObjectType or VariableType for the child. 

The ModellingRule indicates whether a child is Mandatory or Optional. It can also indicate cardinality. Note that the BrowseName is not defined if the cardinality is greater than 1. Figure 12 visually depicts the ObjectType defined in Table 1 along with two instances of the ObjectType.

[Figure: Figure 12 - A Visual Representation of the Sample ObjectType]

4.4 Modelling Approach of ISA-95

The modelling approach for generating an UA model from an existing ISA-95 follows the following general concepts / suggestions.

Review the ISA-95 model documentation.

Map all ISA95 properties to OPC UA Variables and OPC UA VariableTypes, creating OPC UA VariableTypes as needed. Create a subtype of a VariableType whenever the item will be reused multiple times; otherwise just create an instance of the appropriate OPC UA VariableType (Equipment Property Type or PhysicalAssetPropertyType ….). 

Map all ISA Classes and ISA Objects to OPC UA ObjectTypes, creating OPC UA ObjectTypes as needed. Again ObjectType need only be created for Objects where multiple instance of the Object will exist, otherwise simply creating an instance of the appropriate ObjectType (EquipmentType, PhysicalAssetType). 

Create all types as part of a hierarchical set of types, to allow for easier implementation and maintenance.

Convert IDs that are used to indicate a relationship between ISA-95 Model items to OPC UA References. Use the References defined in this specification as needed. Generate Custom References only if an existing reference does not exist, and the Reference provides some unique semantic information.

Reuse existing OPC UA concepts wherever possible, such as Descriptions, Names, EngineeringUnits etc.  These items should not be duplicated as additional ISA properties.

Compare any resulting model to the B2MML model for the same concept. This comparison is to ensure that no concepts were misunderstood or modelled very differently. The goal does include being able to transform a UA model into B2MML and also to transform B2MML Models into UA Models. The two models do not need to be identical, but they need to be transformable.

5 Fundamentals

5.1 Meta-model Mapping Approach

5.1.1 General

ISA-95 defines the meta-models to describe object models using UML notation (See Annex E). This standard defines mapping between the UML notation and the OPC UA meta-model to transform the object model defined in ISA-95 into an OPC UA Address Space Model. (See OPC 10000-3, 0, OPC UA Meta Model)

[Figure: Figure 13 - Meta-model mapping]

5.1.2 ISA95Class

ISA95Class is a concept to represent a classification of ISA95 Resource and is represented by a UML Class and an OPC UA ObjectType (see Table 2).

Table 2 - Transformation rule of an ISA95Class
ISA-95,OPC UA,Description
UMLClass,ObjectType,Structure of the Class is defined by ObjectType.

5.1.3 ISA95Object

ISA95Object is a concept to represent resources like a Role Base Equipment and is represented by a UML Class and an OPC UA ObjectType and OPC UA Objects (see Table 3).

Table 3 - Transformation rule of an ISA95Object
ISA-95,OPC UA,Description
UMLClass,ObjectType,"Structure of the ISA95Object is defined by associated Classes and in some case by a defined ObjectTypes, and an instance of the ISA95Object is represented by an Object of the ObjectType or base ObjectType."
,Object,

5.1.4 ISA95Attribute

ISA95Attribute is a minimum set of industry-independent information and is described in the attribute table defined in ISA-95. ISA-95 doesn't describe an attribute in UML. In OPC UA it can be represented by Attributes, VariableTypes, Variables, and Properties (see Table 4), 

Table 4 - Transformation rule of an ISA95Attribute
ISA-95,OPC UA,Description
Table of ISA95 Attribute,Attribute,"ISA95ID, ISA95Description, and ISA95ValueAttribute are transformed into attributes of Object or DataVariable. Other Attributes are transformed into Properties of the Object or DataVariable."
,Variable,
,VariableType,
,Property,

5.1.5 ISA95Property

ISA95Property is a concept to represent characteristics for domain specific information. Accordingly ISA-95 defines that attributes that are application or industry specific are to be modelled in terms of properties and represented in property classes in the model. ISA-95 doesn't describe a property as an attribute in UML, but describes a property as a Class. In OPC UA it can be represented by VariableTypes and Variables (see Table 5)

Table 5 - Transformation rule of an ISA95Property
ISA-95,OPC UA,Description
UMLClass,VariableType,"Structure of the ISA95Property is defined by a VariableType, and an instance of the ISA95Property is represented by a DataVariable of the VariableType."
,DataVariable,

5.1.6 Complex Value

5.1.6.1 General

OPC UA allows information to be represented as complex Variables (Variable with nested sub-variable) and/or as complex DataTypes, where a DataType has a structure or other special meaning associated with it. Each of the nested Variables can have a value that represents a simple base DataType such as an Integer or can represent a custom DataType such as a Currency or a structure. 

The format of a value is represented by Attributes of Variables. This standard maps all value formats defined in ISA-95 into those attributes.

5.1.6.2 Array value

Arrays of values are represented by DataType, ValueRank, ArrayDimensions, and MaxArrayLength attribute of a VariableType. (See OPC 10000-3). The following examples illustrate the usage of these Attributes:

1. A set of values for a single dimension array of integers with 6 values
2. EBNF:  [ 1 , 2 , 3 , 4 , 5 , 6]
3. OPC UA: DataType=Int32(any), ValueRank=OneDimension(1), ArrayDimensions=6, MaxArrayLength=6.
4. A set of values for a two dimension array of size 2x3
5. EBNF: [ [1 , 2] , [3 , 4] ,[5 , 6]]
6. OPC UA:  DataType=Int32(any), ValueRank= 2, ArrayDimensions=[2,3], MaxArrayLength=6
7. A set of values for a four dimension array of size 2x3x4x5
8. EBNF: omitted for simplicity
9. OPC UA: DataType=Int32(any), ValueRank= 4, ArrayDimensions=[2,3,4,5], MaxArrayLength=120

5.1.6.3 Range value

Ranges of values are represented by Range DataType defined in OPC 10000-8. If the Range is an array, then ValueRank, ArrayDimensions, and MaxArrayLength attributes are utilized to indicate an array.

1. A simple range of values
2. EBNF:	 {0..100}
3. OPC UA : 	DataType=Range, ValueRank= Scalar (-1)
4. A non-continuous range of values
5. EBNF: 	{0 .. 100 , 200 .. 300 , 500 , 600 .. 650}
6. OPC UA : 	DataType=Range, ValueRank= OneDimension (1), ArrayDimensions=4

5.1.6.4 Series value

A set of allowed values is defined in EnumStrings and the EnumValues Standard Property of Enumeration DataType. 

1. A series of values that defines colours.
2. EBNF: 	<Red, Green, Yellow, Blue>
3. OPC UA : 	Array of LocalizedText that is a list of the enumeration strings is set to EnumStrings

5.1.6.5 Structured value

Structured data element is defined in custom DataType derived from Structure DataType or is represented by nested VariableType that has Variables as children.

1. A structured data element represented as flattened Property Name
2. Struct Simple {
3. 	Integer Position;
4. 	Float LastValue;
5. 	Boolean Exists;
6. 	String Comment;}
7. ISA-95: 	Simple.Position, Simple.LastValue, Simple.Exists, Simple.Comment

OPC UA:,"ABC DataType (custom DataType) derived from Structure DataType is defined, with the given structure."

1. A structured data element represented by creating an ISA95Property with no data value with nested child ISA95Properties and identification of element.
2. Struct Simple {
3. 	public int Position;
4. 	public double LastValue;
5. 	public bool Exists;
6. 	public string Comment;}
7. ISA-95: 	Property [ID="Simple"]
8. Property [ID="Simple"]\ Property [ID="Position"]
9. Property [ID="Simple"]\ Property [ID="LastValue"]
10. Property [ID="Simple"]\ Property [ID="Exists"]
11. Property [ID="Simple"]\ Property [ID="Comment"]

OPC UA:,"All ISA95Properties are represented as Variables and Simple property points to Position, LastValue, Exists, and Comment properties by HasComponent or subtypes of HasComponent ReferenceType. (See clause 4.3.8.6)"

A combination of a) and b) where a structured data element represented by creating a ISA95 Property with a data value that is a structured data element and with nested child properties and identification of element (see Figure 14). This is the preferred method for modelling complex information. [Note: the figure flow the template defined in OPC 10000-3 with some extensions defined in Annex F] 

[Figure: Figure 14 - Complex Data Mapping]

5.1.7 ISA95Reference

5.1.7.1 General

ISA95Reference is a concept that represents a relationship between modelling targets and is represented by UML Association and by OPC UA ReferenceType (see Table 6).

Table 6 - Transformation rule of a ISA95Reference
ISA-95,OPC UA,Description
UMLAssociation,ReferenceType,"ISA95Reference is defined by ReferenceType. Name of the association may be a name of ReferenceType, and cardinality of the association may be mapped into a Modelling Rule of target Node of the Reference."
,,

5.1.7.2 UMLAssociation

UMLAssociation represents an association between elements of a class and elements of another or the same class. The UMLAssociation is transformed to subtypes of OPC UA NonHierarchicalReferences (see Table 7).

 Table 7 - Transformation rule of the elements of UMLAssociation
ISA-95,OPC UA,Description
UMLRole,"SourceNode, TargetNode",UMLRole may be transformed into the restrictions of ReferenceType.
UMLCardinality,N/A,Standard ModellingRules only affect instance declaration specified by subtypes of Hierarchical References.
UMLAssociation Name,BrowseName,A name defined in ISA-95 may be changed. InverseName will be defined.

Instance Nodes that are referenced by NonHierarchicalReferences are not instantiated when an instance of an ObjectType or VariableType is created.

5.1.7.3 UMLGeneralization

UMLGeneralization is used to describe that an element of UMLClass is a specialized type of the super UML Class, it mapped to the OPC UA HasSubtype ReferenceType.

5.1.7.4 UMLDependence

UMLDependence is a weak association that is used to describe a modelling element that depends on another modelling element. This standard doesn't support this concept in general terms. Depending on the nature of the dependence it may be modelled as a custom reference.

5.1.7.5 UMLAggregation

UMLAggregation is used to describe that an element of the class is made up of elements of other classes; it is mapped to subtypes of the OPC UA Aggregates ReferenceType (see Table 8).  

Table 8 - Transformation rule of the elements of UMLAggregation
ISA-95,OPC UA,Description
UMLRole,"SourceNode, TargetNode",UMLRole may be transformed into the restrictions of ReferenceType.
UMLCardinality,N/A,Standard ModellingRules only affect instance declaration specified by sub-types of Hierarchical References.
UMLAssociation Name,BrowseName,A name defined in ISA-95 may be changed. InverseName will be defined.

5.1.7.6 UMLComposite

UMLComposite is used to describe a strong form of aggregation, it is mapped to OPC UA HasComponent or subtypes of OPC UA HasComponent ReferenceType (see Table 9).

Table 9 - Transformation rule of the elements of UMLComposite
ISA-95,OPC UA,Description
UMLRole,"SourceNode, TargetNode",UMLRole may be transformed into the restrictions of ReferenceType.
UMLCardinality,ModellingRule,1,Mandatory
,,0..1,Optional
,,0..N,OptionalPlaceholder
,,1..N,MandatoryPlaceholder
UMLAssociation Name,BrowseName,A name defined in ISA-95 may be changed. InverseName will be defined.

5.2 Model Overview


          Figure 15 illustrates an overview of ISA-95 OPC UA Information Model. This overview is not complete, additional figures in later section will provide additional details of the information model. ISA-95 Base Information Model defines all models that are commonly utilized in this standard. This model includes a data representation model that is based on UN/CEFACT Core Data Type (CDT) (see UN/ECE). ISA-95 Common Object Model defines the models that represent all ISA95Resources and relationship between them.

[Figure: Figure 15 - ISA-95 OPC UA Information Model]

6 ISA-95 Data Representation Model

6.1 General

ISA-95 is an abstract specification that has no data model. The B2MML implementation further refined the ISA-95 standard to include a set of standard data types. They selected the UN/CEFACT for this data type definition. These standard data type are now the default data type of ISA-95 Models In order to support transformation between the B2MML mapping and the OPC UA mapping of the ISA-95 Information models a mapping of UN/CEFACT is required.

The UN/CEFACT core component types are a common set of types that define specific terms with semantic meaning, such as the meaning of a quantity, currency, amount, identifier, and language. The UN/CEFACT core components were defined in a core components technical specification (CCTS) developed by the ebXML project now organized by UN/CEFACT and ISO TC 154. This definition also includes supplementary components which provide metadata that refine the value domain. See CCTS for additional information.

This standard defines a data representation model that is compatible with CCTS. The value of a content component is represented by the Value Attribute of a Variable, and the supplemental components that are defined in CCTS are represented as Properties of the DataType. In addition these supplemental Properties may optionally be defined for Variables. 

Most of the CDTs, defined in CCTS, are defined as CDT DataTypes in this standard but some CDTs are mapped to OPC UA Built-in DataTypes directly. 

All supplemental Properties defined as part of a CDT DataType include the definition of a default value. This allows a Server to not require the addition of the optional Properties, while still allowing a client to obtain the value for the CDT DataType supplemental Properties. However, for some DataTypes or VariableTypes the supplemental Properties may have different values on instances than the default value. For example, a Unit of Measure type depends upon measurement data. In this case, the Server shall duplicate the supplemental Property from the CDT DataType and to the Variable. A client shall try to read the supplemental Property from the Variable first, if the Property does not exist on the variable than the Client shall read the supplemental Property from the CDT DataType. 

[Figure: Figure 16 - Basic data representation model]

Third parties may define VariableTypes that rely on CDT DataTypes to enhance data representation methodology. This approach will allow the use of generic clients that support performing actions based on a type system (programming against a type system). Figure 17 illustrates a type definition based on a CDT type. This is an enhanced feature but this standard recommends using the enhanced representation instead of the basic representation model.

[Figure: Figure 17 - Enhanced data representation model]


          Figure 18 illustrates an example of the Amount and the Measure types defined in CCTS. In this example, a value of Currency Property is commonly used in UA Server but a value of Unit Property relates to a measurement value that is temperature. 

[Figure: Figure 18 - Example of CDT implementation]

6.2 Content Component DataType

6.2.1 General

CCTS defines a finite set of primitive data types that shall be used for a Content Component. These data types are mapped to OPC UA CC (Content Component) DataTypes which are OPC UA Built-in DataTypes or DataTypes defined in the following clauses. Table 10 defines mapping between the primitive data types for the Content Component and the CC DataTypes.

Table 10 - Built-in data types
CCTS Primitive data type,OPC UA CC DataType,Description,Definition
Binary,ByteString,,OPC 10000-3
Boolean,Boolean,,OPC 10000-3
Decimal,Decimal,,Clause 6.2.4
,DecimalString,,Clause 6.2.5
Double,Double,,OPC 10000-3
Float,Float,,OPC 10000-3
Integer,Integer,"SByte, Int16, Int32, Int64",OPC 10000-3
NormalizedString,NormalizedString,,Clause 6.2.7
String,String,,OPC 10000-3
,LocalizedText,,OPC 10000-3
TimeDuration,DurationString,,Clause 6.2.6
TimePoint,DateString,,Clause 6.2.2
,TimeString,,Clause 6.2.6
Token,N/A,,N/A
N/A,CurrencyCode,Used to represent code for currency,Clause 6.2.2

6.2.2 CurrencyCode

This is a structured DataType which represents a currency code. Its elements are defined in Table 11.

Table 11 - CurrencyCode DataType structure
Name,Type,Description
CurrencyCode,Structure,
namespaceUri,String,"Identifies the organization (company, standards organization) that defines the currency code. Default is http://www.opcfoundation.org/UA/Currency/ISO4217:2008"
unitId,Int32,"Numeric id from the ISO4217 table. This element is optional. Default value shall be ""-1"" that indicates that this element isn't applicable."
charId,Byte[3],The CharacterId from the ISO4217 table. This has a fixed length of 3 characters as defined by ISO4217:2008.The allowed values in the Byte are the ASCI codes representing each character. The range of ASCI characters that are allowed is defined in the ISO4217 table.
displayName,LocalizedText,Symbol if one is defined otherwise the same as the charid.
Description,LocalizedText,Contains the full name of the currency such as Australian Dollar or Yuan Renminbi

Its representation in the Address Space is defined in Table 12.

Table 12 - CurrencyCode Definition
Attributes,Value
BrowseName,CurrencyCode

6.2.3 DateString

This DataType defines a value which is a day in the Gregorian calendar in string. Lexical representation of the string conforms to ISO 8601-2000.

Table 13 - DateString Definition
Attribute,Value
BrowseName,DateString
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the String defined in OPC 10000-3

According to ISO 8601-2000, 'calendar date representations are in the form [YYYY-MM-DD]. [YYYY] indicates a four-digit year, 0000 through 9999. [MM] indicates a two-digit month of the year, 01 through 12. [DD] indicates a two-digit day of that month, 01 through 31. For example, "the 5th of April 1981" may be represented as either "1981-04-05" in the extended format or "19810405" in the basic format.'

The standard also allows for calendar dates to be written with reduced precision. For example, one may write "1981-04" to mean "1981 April", and one may simply write "1981" to refer to that year or "19" to refer to the century from 1900 to 1999 inclusive.

Although the standard allows both the YYYY-MM-DD and YYYYMMDD formats for complete calendar date representations, if the day [DD] is omitted then only the YYYY-MM format is allowed. By disallowing dates of the form YYYYMM, the standard avoids confusion with the truncated representation YYMMDD (still often used).

6.2.4 Decimal

This DataType defines a decimal value. The format of this value conforms to the following formula

 (-1)sign x coefficient x 10exponent

Table 14 - Decimal Definition
Attribute,Value
BrowseName,Decimal
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the SByte defined in OPC 10000-3

For this release the OPC UA stacks and infrastructure does not support Decimal as a base type, thus this type must be mapped to a ByteString and the ByteString must be passed to the SDK and/or Stack. This DataType has to be handled by the application.

Decimal can be encoded in a number of ways and can be defined to have 32, 64 and 128 varieties. Since the OPC UA stacks do not natively support this encoding only a single Decimal type is being defined. This will allow the stacks in the future to be expanded to support Decimal32, Decimal64 and Decimal128. The encoding of decimal is also defined by more than one group using different encodings. The binary encoding being used for this release (and will always be used for the plain decimal binary string encoding) is a string that is 128 bit and follows the IEC TR 24732 definition for a decimal. It is summarised in the table below.

Table 15 - Decimal Definition
Parameter,decimal
"k, storage width in bits",128
"p, precision in digits",34
Emax,6144
"bias, E - q",6176
Encoding parameters
sign bit,1
"w +5, combination field width in bits",17
"t, trailing significant field width in bits",110
"k, storage width in bits",128
,

6.2.5 DecimalString

This primitive DataType defines a value which can be represented by decimal number in string. Lexical representation of the string conforms to W3C XML Schema Definition Language (XSD) 1.1 Part 2: DataTypes.

Table 16 - DecimalString Definition
Attribute,Value
BrowseName,DecimalString
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the String defined in OPC 10000-3

OPC UA Applications may have the responsibility to encode / decode the DecimalString to an appropriate data type which is supported by the application's platform. The DecimalString is a numeric string with an optional sign and decimal point.

6.2.6 DurationString

This DataType defines a value which is a string representation of a duration of time. It conforms to lexical rules in ISO 8601-2000.

Table 17 - DurationString Definition
Attribute,Value
BrowseName,DurationString
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the String defined in OPC 10000-3

According to ISO 8601-2000 'Durations are represented by the format P[n]Y[n]M[n]DT[n]H[n]M[n]S or P[n]W as shown to the right. In these representations, the [n] is replaced by the value for each of the date and time elements that follow the [n]. Leading zeros are not required, but the maximum number of digits for each element should be agreed to by the communicating parties. The capital letters P, Y, M, W, D, T, H, M, and S are designators for each of the date and time elements and are not replaced.


            P is the duration designator (historically called "period") placed at the start of the duration representation. 


            Y is the year designator that follows the value for the number of years. 


            M is the month designator that follows the value for the number of months. 


            W is the week designator that follows the value for the number of weeks. 


            D is the day designator that follows the value for the number of days. 


            T is the time designator that precedes the time components of the representation. 


            H is the hour designator that follows the value for the number of hours. 


            M is the minute designator that follows the value for the number of minutes. 


            S is the second designator that follows the value for the number of seconds. 

For example, "P3Y6M4DT12H30M5S" represents a duration of "three years, six months, four days, twelve hours, thirty minutes, and five seconds". Date and time elements including their designator may be omitted if their value is zero, and lower order elements may also be omitted for reduced precision. For example, "P23DT23H" and "P4Y" are both acceptable duration representations'

6.2.7 NormalizedString

This DataType defines a value which is a normalized string. Some Unicode characters have multiple equivalent binary representations consisting of sets of combining and/or composite Unicode characters. The Unicode standard defines a process called normalization that returns one binary representation when given any of the equivalent binary representations of a character. The Win32 and the .NET Framework currently support normalization forms C, D, KC, and KD, as defined in Annex15. This definition of NormalizedString uses Normalization Form C for all content, because this form avoids potential interoperability problems arising from the use of canonically equivalent, yet different, character sequences in document formats

 Table 18 - NormalizedString Definition
Attribute,Value
BrowseName,NormalizedString
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the String defined in OPC 10000-3

6.2.8 TimeString

This DataType defines a value which is the string representation of a time. It conforms to lexical rules in ISO 8601-2000.

 Table 19 - TimeString Definition
Attribute,Value
BrowseName,TimeString
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition
Subtype of the String defined in OPC 10000-3

ISO 8601 uses the 24-hour clock system. The basic format is [hh][mm][ss] and the extended format is [hh]:[mm]:[ss].

[hh] refers to a zero-padded hour between 00 and 24 (where 24 is only used to notate midnight at the end of a calendar day). 

[mm] refers to a zero-padded minute between 00 and 59. 

[ss] refers to a zero-padded second between 00 and 60 (where 60 is only used to notate an added leap second). 

So a time might appear as either "134730" in the basic format or "13:47:30" in the extended format.

It is also acceptable to omit lower order time elements for reduced accuracy: [hh]:[mm], [hh][mm] and [hh] are all used.

Midnight is a special case and can be referred to as both "00:00" and "24:00". The notation "00:00" is used at the beginning of a calendar day and is the more frequently used. At the end of a day use "24:00"

6.3 Core Data Type DataType

6.3.1 General

All data types defined as CDT are mapped to CDT DataTypes or CC DataTypes. Table 20 defines mapping of data types between CCTS and OPC UA.

Table 20 - CDT Data types
CDT,OPC UA,Description,Category,Definition
Amount,CDTAmount,,CDT,Clause 6.3.2
Binary Object,CDTBinaryObject,,CDT,Clause 6.3.3
Code,CDTCode,,CDT,Clause 6.3.4
Date,DateString,,CC,Clause 6.2.2
Date Time,CDTDateTime,,CDT,OPC 10000-3
Duration,DurationString,,CC,Clause 6.2.6
Graphic,CDTGraphic,,CDT,Clause 6.3.6
Identifier,CDTIdentifier,,CDT,Clause 6.3.7
Indicator,Boolean,,CC,OPC 10000-3
Measure,CDTMeasure,,CDT,Clause 6.3.7
Name,LocaizedText,"Language supplemental is mapped to a ""locale"" element.",CC,OPC 10000-3
Number,Number,"Decimal, Double, Float, Int16, Int32, and Int64 are allowed.",CC,OPC 10000-3
Ordinal,CDTOrdinal,,CDT,Clause 6.3.9
Percent,CDTMeasure,"Codes according to only percent shall be used. (e.g. ""P1"")",CDT,Clause 6.3.7
Picture,CDTPicture,,CDT,Clause 6.3.10
Quantity,Number,"Decimal, Double, Float, Int16, Int32, and Int64 are allowed.",CC,OPC 10000-3
Rate,CDTRate,,CDT,Clause 6.3.11
Ratio,Number,"Decimal, Double, Float, Int16, Int32, and Int64 are allowed.",CC,OPC 10000-3
Sound,CDTSound,,CDT,Clause 6.3.12
Text,LocalizedText,"Language supplemental is mapped to a ""locale"" element.",CC,OPC 10000-3
Time,TimeString,,CC,Clause 6.2.8
Value,BaseDataType,"Decimal, Double, Float, Int16, Int32, Int64 or String is allowed. (other Variant types may also be supported)",CC,OPC 10000-3
Video,CDTVideo,,CDT,Clause 6.3.13

Semantic of CDT that is mapped to CC DataType may be defined in ObjectTypes or VariableTypes.

6.3.2 CDTAmountDecimal

The CDTAmountDecimal is a DataType that conforms to Amount type. Table 21 defines the DataTypes.

Table 21 - DataTypes for Amount 
Content Component data type for Amount,OPC UA CC DataType,OPC UA CDT DataType
Decimal,Decimal,CDTAmountDecimal
Double,,
Float,,
Integer,,

The CDTAmountDecimal is a number of monetary units specified in a currency. CDTAmountDecimal type is "used to represent amounts, such as costs, remunerations, and fees" from CCTS. All CC types (integer, float…) are mapped to a decimal value.

Table 22 - CDTAmountDecimal Definition
Attribute,Value
BrowseName,CDTAmountDecimal
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Decimal
HasCDTSupplemental,Variable,Currency,CurrencyCode,PropertyType,Optional

6.3.3 CDTBinaryObject

The DataType CDTBinaryObject is a subtype of ByteString that defines CCTS binary data based on MIME type. The CDTBinaryObject type is "used for embedding documents such as Word, PDF and/or engineering documents" from CCTS. CDTBinaryObject is differentiated from its related types - CDTGraphic, CDTPicture, CDTSound, and CDTVideo.

Table 23 - CDTBinaryObject Definition
Attribute,Value
BrowseName,CDTBinaryObject
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ByteString defined in OPC 10000-3
HasCDTSupplemental,Variable,MIMEContentType,String,PropertyType,Optional
HasCDTSupplemental,Variable,CharacterSet,String,PropertyType,Optional
HasCDTSupplemental,Variable,Encoding,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,CharacterSetListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,CharacterSetListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,CharacterSetListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,EncodingListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,EncodingListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,EncodingListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,Filename,String,PropertyType,Optional


            MIMEContentType defines the Multipurpose Internet Mail Extensions (MIME) media type of the binary object. This standard recommends use of text code defined in IETF RFC2045, IETF RFC2046 and IETF RFC2047 for the MIME. In this case the MIMEContentType is actually referencing the Content-Type that is defined as part of the MIME type and commonly used as a reference to a specific MIME. The top-level media type is used to declare the general type of data, while the subtype specifies a specific format for that type of data. Thus, a media type of "image/xyz" is enough to tell a user agent that the data is an image, even if the user agent has no knowledge of the specific image format "xyz". Such information can be used, for example, to decide whether or not to show a user the raw data from an unrecognized subtype such an action might be reasonable for unrecognized subtypes of "text", but not for unrecognized subtypes of "image" or "audio".


            CharacterSet defines a specific character set of text data if MIME is text. This standard recommends use of text code defined in IANA for the CharacterSet. 


            Encoding defines an encoding/decoding mechanism of the Binary Object. If contents of the Binary Object are encoded in specific formats, UA Server represents the formats using this supplemental to indicate a code to identify the encoding. Generally, UA Server doesn't need to encode Binary Objects since the UA Stack always Encodes Messages in the appropriate format defined in OPC 10000-6. This standard recommends the use of text codes defined in IETF RFC2045, IETF RFC2046 and IETF RFC2047 for the Encoding.


            MIMEListId represents the identification of a list of codes (refers to the MIMEContentType).


            MIMEListAgencyId represents the identification of the agency that manages the code list (refers to the MIMEContentType).


            MIMEListVersionId represents the identification of the version of the list of codes (refers to the MIMEContentType).

CharacterSetListId represents the identification of a list of codes (refers to the CharacterSet).

CharacterSetListAgencyId represents the identification of the agency that manages the code list (refers to the CharacterSet).

CharacterSetListVersionId represents the identification of the version of the list of codes (refers to the CharacterSet).


            EncodingListId represents the identification of a list of codes (refers to the Encoding).


            EncodingListAgencyId represents the identification of the agency that manages the code list (refers to the Encoding).


            EncodingListVersionId represents the identification of the version of the list of codes (refers to the Encoding).


            Filename defines the recommended file name that can be used to store data. The file name is usually the name of the original data file that is represented in the Binary Object. 

6.3.4 CDTCode

The DataType CDTCode is a subtype of String that defines CCTS Code type. The CDTCode Type is a character string (letters, figures or symbols) that for brevity and/or language independence may be used to represent or replace a definitive value or text of an attribute" from CCTS.

OPC UA Client may have the code list as its implementation or OPC UA Server may provide it in an Address Space. OPC UA Application will get symbol of a code from the code list in any case. 

Table 24 - CDTCode Definition
Attribute,Value
BrowseName,CDTCode
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the String defined in OPC UA Part3
HasCDTSupplemental,Variable,ListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,ListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,ListVersionId,String,PropertyType,Optional


            ListId represents the identification of a list of codes.


            ListAgencyId represents the identification of the agency that manages the code list. 


            ListVersionId represents the identification of the version of the list of codes.

6.3.5 CDTDateTime

The DataType CDTDateTime is a subtype of DateTime that defines CCTS DateTime. The DateTime identifies a date and time of day to various common resolutions: year, month, week, day, hour, minute, second, and fraction of second from CCTS and is used to represent a Gregorian calendar date with UTC time.

Table 25 - CDTDateTime Definition
Attribute,Value
BrowseName,CDTDateTime
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the UtcTime defined in OPC 10000-3
HasCDTSupplemental,Variable,Timezone,String,PropertyType,Optional
HasCDTSupplemental,Variable,DaylightSavings,Boolean,PropertyType,Optional

The Timezone can be used to indicate the time zone associated with the data source. The UtcTime value is in GMT and does not have a time zone factor applied. This parameter is provided to allow a client to display the provided time in the time zone that was associated with to original value.

The DaylightSavings can be used to indicate daylights saving if DaylightSavings was in effect when for the given DateTime. The UtcTime value is in GMT and does not have a Timezone factor applied. This parameter is provided to allow a client to display the provided time with the daylight savings time adjustment that was associated with to original value. 

6.3.6 CDTGraphic

The DataType CDTGraphic is a subtype of ByteString that defines CCTS Graphic type. The CDTGraphic type is used to represent binary data and binary files for vector based graphics, such as CAD drawings, diagrams, graphs, mathematical curves and charts from CCTS.

Table 26 - CDTGraphic Definition
Attribute,Value
BrowseName,CDTGraphic
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ByteString defined in OPC 10000-3
HasCDTSupplemental,Variable,MIMEContentType,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,Filename,String,PropertyType,Optional


            MIMEContentType defines the Multipurpose Internet Mail Extensions (MIME) media type of the binary object. For additional information see 6.3.3


            MIMEListId represents the identification of a list of codes (refers to the MIMEContentType).


            MIMEListAgencyId represents the identification of the agency that manages the code list (refers to the MIMEContentType).


            MIMEListVersionId represents the identification of the version of the list of codes (refers to the MIMEContentType).


            Filename defines the recommended file name that can be used to store data. The file name is usually the name of the original data file that is represented in the Binary Object. 

6.3.7 CDTIdentifier

The DataType CDTIdentifier is a subtype of String that defines CCTS Identifier Type. The CDTIdentifier type is an identifier is a character string used to uniquely identify one instance of an object within an identification scheme that is managed by an agency from CCTS.

Table 27 - CDTIdentifier Definition
Attribute,Value
BrowseName,CDTIdentifier
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the String defined in OPC 10000-3
HasCDTSupplemental,Variable,SchemeId,String,PropertyType,Optional
HasCDTSupplemental,Variable,SchemeVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,SchemeAgencyId,String,PropertyType,Optional


            SchemeId represent the identification of the identifier scheme.


            SchemeVersionId represents the identification of the version of the identifier scheme.


            SchemeAgencyId represents the identification of the agency that manages the identifier scheme.

6.3.8 CDTMeasure

The CDTMeasure is a generic term for DataTypes that conform to the Measure type. The actual DataTypes are defined separately according to each primitive data type of content component. Table 28 defines the DataTypes.

Table 28 - DataTypes according to CDTMeasure
Content Component data type,OPC UA CC DataType,OPC UA CDT DataType
Decimal,Decimal,CDTMeasureDecimal
Double,Double,CDTMeasureDouble
Float,Float,CDTMeasureFloat
Integer,Int16,CDTMeasureInt16
,Int32,CDTMeasureInt32
,Int64,CDTMeasureInt64

The CDTMeasure is a numeric value determined by measuring an object along with the specified unit of measure. It "is used to represent a kind of physical dimension such as temperature, length, speed, width, weight, volume, latitude of an object. More precisely, it should be used to measure intrinsic or physical properties of an object seen as a whole according to CCTS.

Table 29 - CDTMeasure Definition
Attribute,Value
BrowseName,One of the OPC UA CDT DataType value in  Table 28
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the one of the OPC UA CC DataTypes Table 28
HasCDTSupplemental,Variable,Unit,EUInformation,PropertyType,Optional


            Unit defines measurement units defined in OPC 10000-8. EUInformation identifies unit by three letters specified in Unit element. This rule is reasonable if code set of Unit is based on UNECE. Otherwise, code shall be set into Display, and Unit shall be set to (-1).

NOTE: OPC 10000-8 defines EUInformation DataType to indicate code of the unit defined in UN/ECE. This standard uses the EUInformation to represent code defined in UN/ECE instead of CDTCode.

6.3.9 CDTOrdinal

The DataType CDTOrdinal is a subtype of Int32 that defines CCTS Ordinal type. It is an assigned mathematical number that represents order or sequence according to CCTS.

Table 30 - CDTOrdinal Definition
Attribute,Value
BrowseName,CDTOrdinal
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Int32 defined in OPC 10000-3

6.3.10 CDTPicture

The DataType CDTPicture is a subtype of Image that defines CCTS Picture type. It is a visual representation of a person, object, or scene in binary notation (octets). It should be used for embedding binary data of pictures such as photos, art, and clip art according to CCTS. If no supplemental data is to be provided it is also acceptable to directly map any CDTPicture data to a subtype of the standard OPC UA Image dataType (ImageBMP, ImageGIF, ImageJPG, ImagePNG).

Table 31 - CDTPicture Definition
Attribute,Value
BrowseName,CDTPicture
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Image defined in OPC 10000-3
HasCDTSupplemental,Variable,MIMEContentType,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,Filename,String,PropertyType,Optional

The MIMEContentType supplemental property is rarely used, since in most cases the picture binary blob includes header information that includes the MIME information. Most applications can just obtain the information directly from the picture blob


            MIMEContentType defines the Multipurpose Internet Mail Extensions (MIME) media type of the binary object. For additional information see 6.3.3


            MIMEListId represents the identification of a list of codes (refers to the MIMEContentType).


            MIMEListAgencyId represents the identification of the agency that manages the code list (refers to the MIMEContentType).


            MIMEListVersionId represents the identification of the version of the list of codes (refers to the MIMEContentType).


            Filename defines the recommended file name that can be used to store data. The file name is usually the name of the original data file that is represented in the Binary Object. 

6.3.11 CDTRate

The CDTRate is a generic term for DataTypes that conform to the Rate type. The actual DataTypes are defined separately according to each primitive data type of content component. Table 32 defines the DataTypes.

Table 32 - DataTypes according to CDTRate
Content Component data type,OPC UA CC DataType,OPC UA CDT DataType
Decimal,Decimal,CDTRateDecimal
Double,Double,CDTRateDouble
Float,Float,CDTRateFloat
Integer,Integer,CDTRateInt32

The CDTRate is a quantity, amount, frequency, or dimensionless factor, measured against an independent base unit, expressed as a quotient. In addition CCTS describe it is used to represent the numerical quotient resulting from a comparison of two independent things such as a quantity measured with respect to another measured quantity such as a rate of speed, a measure of a part with respect to a whole - a proportion such as the mortality rate, a tax rate, the cost per unit of a commodity or service or a charge or payment calculated in relation to a particular sum or quantity such as interest rates. The quotient is calculated by taking into account the Rate.Multiplier.Value and Rate.Base.Multiplier. Value supplementary components that affect the unit codes used at the numerator and the denominator.

Table 33 - CDTRate Definition
Attribute,Value
BrowseName,One of the OPC UA CDT DataType values in  Table 32)
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the CC DataType according to the BrowseName
HasCDTSupplemental,Variable,Multiplier,Double,PropertyType,Optional
HasCDTSupplemental,Variable,Unit,EUInformation,PropertyType,Optional
HasCDTSupplemental,Variable,Currency,CurrencyCode,PropertyType,Optional
HasCDTSupplemental,Variable,BaseMultiplier,Double,PropertyType,Optional
HasCDTSupplemental,Variable,BaseUnit,EUInformation,PropertyType,Optional
HasCDTSupplemental,Variable,BaseCurrency,CurrencyCode,PropertyType,Optional


            Multiplier defines multiplier of the numerator. The default value is "1" if the element is omitted.


            Unit defines the unit of measure of the numerator. The Unit is represented in EUInformation defined in OPC UA Part8.


            Currency defines the currency unit of the numerator.


            BaseMultiplier defines multiplier of the denominator. The default value is "1" if the element is omitted.


            BaseCurrency defines the currency unit of the denominator BaseUnit defines the unit of measure of the denominator. The BaseUnit is represented in EUInformation defined in OPC UA Part8.

6.3.12 CDTSound

The DataType CDTSound is a subtype of ByteString that defines CCTS Sound type. It is any form of an audio file such as audio recordings in binary notation according to CCTS.

Table 34 - CDTSound Definition
Attribute,Value
BrowseName,CDTSound
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ByteString defined in OPC 10000-3
HasCDTSupplemental,Variable,MIMEContentType,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,Filename,String,PropertyType,Optional

The MIMEContentType supplemental property is rarely used, since in most cases the sound binary blob includes header information that includes the MIME information. Most applications can just obtain the information directly from the sound blob


            MIMEContentType defines the Multipurpose Internet Mail Extensions (MIME) media type of the binary object. For additional information see 6.3.3


            MIMEListId represents the identification of a list of codes (refers to the MIMEContentType).


            MIMEListAgencyId represents the identification of the agency that manages the code list (refers to the MIMEContentType).


            MIMEListVersionId represents the identification of the version of the list of codes (refers to the MIMEContentType).


            FileName defines the recommended file name that can be used to store data. The file name is usually the name of the original data file that is represented in the Binary Object.

6.3.13 CDTVideo

The DataType CDTVideo is a subtype of ByteString that defines CCTS Video type. It is a recording, reproducing or broadcasting of visual images on magnetic tape or digitally in binary notation.

Table 35 - CDTVideo Definition
Attribute,Value
BrowseName,CDTVideo
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ByteString defined in OPC 10000-3
HasCDTSupplemental,Variable,MIMEContentType,CDTCode,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListAgencyId,String,PropertyType,Optional
HasCDTSupplemental,Variable,MIMEListVersionId,String,PropertyType,Optional
HasCDTSupplemental,Variable,Filename,String,PropertyType,Optional

The MIMEContentType supplemental property is rarely used, since in most cases the Video blob includes header information that includes the MIME information. Most applications can just obtain the information directly from the Video blob


            MIMEContentType defines the Multipurpose Internet Mail Extensions (MIME) media type of the binary object. For additional information see 6.3.3


            MIMEListId represents the identification of a list of codes (refers to the MIMEContentType).


            MIMEListAgencyId represents the identification of the agency that manages the code list (refers to the MIMEContentType).


            MIMEListVersionId represents the identification of the version of the list of codes (refers to the MIMEContentType).


            Filename defines the recommended file name that can be used to store data. The file name is usually the name of the original data file that is represented in the Binary Object. 

7 ISA-95 Base Information Model

7.1 Overview


          Figure 19 illustrates overview of the ISA-95 Base Information Model. 

[Figure: Figure 19 - ISA-95 Base Information Model Overview]

7.2 Test Specification Information

The test specification is a definition of a test to ensure the requirements of the ISA95Objects. The test specification may be associated with a subtype of ISA95Class, ISA95ClassProperty, ISA95Object, or ISA95Property.

The test specification is represented as Object and doesn't define elements that represent contents of the test specification. Thus, third party shall create a subtype of the test specification to describe particular test specification (see Figure 20).

[Figure: Figure 20 - Test Specification Information]

For example, the subtype of test specification might have an Object of FileType (defined in OPC 10000-5) that indicates a file for the document that describes a test specification. If a test specification is stored as a file. This type is sub-typed as part of the individual data models to allow easy identification of the type of test specification being referenced, i.e. Equipment Test specification or Physical Asset test specification. It is envisioned that implementers of ISA-95 Models would create subtypes of the data model specific test specification.

7.3 Test Result Information

The test result is the result from an execution of a test specification. An ISA95Property may have a variable that provides the test result. These test results could be time series data that would be accessed by standard Attribute Services as defined in OPC UA Part4.

The test result is represented as DataVariable. The DataType of the VariableType is a structure that represents the various elements of the test result. (See Figure 21 for an example).

[Figure: Figure 21 - Test Result Information]

The test results listed in the figure are a minimum set of information that all test result shall include, but individual systems may provide their own structure that includes additional information. For example some systems may require the name of the person that conducted the test and the qualification that the person had. A new structure can be created that includes all of the original items along with a field for the person information and a field for the person's qualifications. The new record can then be used for the test results.

7.4 DataTypes

7.4.1 ISA95EquipmentElementLevelEnum

This DataType is an enumeration that defines the equipment element levels defined in ISA-95. Its values are defined in a below table. 

NOTE: Note: for enumeration DataTypes it is recommended that variables that use the enumeration also expose the EnumStrings property. This property allows a client to easily translate the enumeration (integer value) to a string for display (see OPC 10000-3).

Table 36 - ISA95EquipmentElementLevelEnum Values
Value,Description
ENTERPRISE_0,An enterprise is a collection of sites and areas and represents the top level of a role based equipment hierarchy.
SITE_1,"A site is a physical, geographical, or logical grouping determined by the enterprise. It may contain areas, production lines, process cells, and production units."
AREA_2,"An area is a physical, geographical, or logical grouping determined by the site. It may contain work centres such as process cells, production units, production lines, and storage zones."
PROCESSCELL_3,Process cells are the low level of equipment typically scheduled by the Level 4 and Level 3 functions for batch manufacturing processes. The definitions for process cells are contained in IEC 61512-1.
UNIT_4,Units are low level of equipment typically scheduled by the Level 4 and Level 3 functions for batch manufacturing processes and continuous manufacturing processes. The definition of the unit for batch manufacturing processes is contained in IEC 61512-1.
PRODUCTIONLINE_5,Production lines are low levels of equipment typically scheduled by the Level 4 or Level 3 functions for discrete manufacturing processes.
WORKCELL_6,Work cells are low levels of equipment typically scheduled by the Level 4 or Level 3 functions for discrete manufacturing processes.
PRODUCTIONUINT_7,Production units are the lowest level of equipment typically scheduled by the Level 4 or Level 3 functions for continuous manufacturing processes.
STORAGEZONE_8,"Storage zones are low level of material movement equipment typically scheduled by the Level 4 and Level 3 functions for discrete, batch and continuous manufacturing processes."
STORAGEUNIT_9,"Storage units are low level of material movement equipment typically scheduled by the Level 4 and Level 3 functions for discrete, batch and continuous manufacturing processes."
WORKCENTER_10,Work centres are typically the grouping of equipment scheduled by the Level 4 or Level 3 functions.
WORKUNIT_11,A work unit is any element of the equipment hierarchy under a work centre. Work units are the lowest form of elements in an equipment hierarchy that are typically scheduled by Level 3 functions.
EQUIPMENTMODULE_12,"An equipment module entity is an engineered subdivision of a process cell, a unit, or another equipment module. The definition of the equipment module is contained in IEC 61512-1."
CONTROLMODULE_13,"A control module entity is an engineered subdivision of a process cell, a unit, an equipment module, or another control module. The definition of the equipment module is contained in IEC 61512-1."
OTHER_14,"The types of work centres may be extended when required for application specific role based equipment hierarchies where the defined types do not apply. In that case, the equipment element level shall be specified as this value, and actual value that identifies the level shall be specified by OtherValue Property of ISAHierarchyScopeType defined in 7.4.1. When a new type is added it shall maintain the same relationship within the hierarchy as the defined work centre types (within an area and contains work units)."

Its representation in the OPC UA AddressSpace is defined in a below table.

Table 37 - ISA95EquipmentElementLevelEnum Definition
Attributes,Value
BrowseName,ISA95EquipmentElementLevelEnum

7.4.2 ISA95TestResultMeasurementDataType

This structure contains elements that records the result from the execution of a test identified in a Test Specification.

Table 38 - ISA95TestResultMeasurementDataType Structure
Name,Type,Description
ISA95TestResultMeasurementDataType,Structure,Information that describes the test record.
Id,NodeId,Identification associated with the test result.
TestResultDescription,LocalizedText,Additional information or description about the result.
Date,DateTime,Date and time of the test. (may be different then Time stamp of the value - which would be when it was recorded)
Result,BaseDataType,The result of qualification test.
ResultUnitOfMeasure,EUInformation,The unit of measure of the associated test result.
Expiration,DateTime,The date of the expiration of the test result.

Its representation in the AddressSpace is defined in a below table.

Table 39 - ISA95TestResultMeasurementDataType Definition
Attributes,Value
BrowseName,ISA95TestResultMeasurementDataType

7.4.3 ISA95TestResultDataType

This structure contains elements that records the result from the execution of a test identified in a Test Specification. This data type shall be the default DataType for test results.

Table 40 - ISA95TestResultDataType Structure
Name,Type,Description
ISA95TestResultDataType,Structure,Information that describes the test record.
Id,NodeId,Identification associated with the test result.
TestResultDescription,LocalizedText,Additional information or description about the result.
Date,DateTime,Date and time of the test. (may be different then Time stamp of the value - which would be when it was recorded)
Result,BaseDataType,The result of qualification test.
ResultUnitOfMeasure,String,The unit of measure of the associated test result.
Expiration,DateTime,The date of the expiration of the test result.

Its representation in the AddressSpace is defined in a below table.

Table 41 - ISA95TestResultDataType Definition
Attributes,Value
BrowseName,ISA95TestResultDataType

7.5 VariableTypes

7.5.1 Overview

The section defines common variable types that are used by multiple section of the ISA specification (i.e. equipment and physical assets etc.) In some cases these types define a generic version of the variable that will be further customized in the specific section, i.e. equipment or physical asset variable section.

The variable types defined in the following sections make use of reference types that are defined in section 0. These reference types provide specific semantic information. To fully understand the Variable or Object models it may be required to review these reference descriptions.

7.5.2 ISA95ClassPropertyType

The ISA95ClassPropertyType is an abstract VariableType that cannot be used directly. It must be subtyped to be used. It is a subtype of BaseDataVariableType defined in OPC 10000-5. 

This VariableType is used to define an ISA95ClassProperty for an ISA95Class. 

Table 42 - ISA95ClassPropertyType definition
Attribute,Value
BrowseName,ISA95ClassPropertyType
IsAbstract,True
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5
HasISA95Attribute,Variable,Key,CDTIdentifier,BaseDataVariableType,Optional


            The Key defines an Id to differentiate between the different values. When multiple values are stored to the Value attribute this ISA95Attribute is used. For example a value may be a series of numbers, such as a series of peak values from a spectrometer.

7.5.3 ISA95PropertyType

The ISA95PropertyType is an abstract VariableType that cannot be used directly. It must be subtyped to be used. It is a subtype of BaseDataVariableType defined in OPC 10000-5. 

This VariableType is used to define an ISA95Property for an ISA95Object. 

Table 43 - ISA95PropertyType definition
Attribute,Value
BrowseName,ISA95PropertyType
IsAbstract,True
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5
HasISA95Attribute,Variable,Key,CDTIdentifier,BaseDataVariableType,Optional
,,,,,


            Key defines an Id to differentiate between the different values. When multiple values are stored to Value attribute this ISA95Attribute is used. For example a value may be a series of numbers, such as a series of peak values from spectrometer.

7.5.4 ISA95TestResultType

The ISA95TestResultdType is a concrete VariableType that can be used directly. It is a subtype of BaseDataVariableType defined in OPC 10000-5. 

This VariableType indicates the test results. Value attribute of this DataVariable is structured data. However, each element of the structure can be accessed via Properties.

Table 44 - ISA95TestResultType definition
Attribute,Value
BrowseName,ISA95TestResultType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5
HasISA95Attribute,Variable,Id,NodeId,PropertyType,Mandatory
HasISA95Attribute,Variable,ResultDescription,LocalizedText,PropertyType,Mandatory
HasISA95Attribute,Variable,TestDate,DateTime,PropertyType,Mandatory
HasISA95Attribute,Variable,Result,BaseDataType,PropertyType,Mandatory
HasISA95Attribute,Variable,ResultUnitOfMeasure,BaseDataType,PropertyType,Mandatory
HasISA95Attribute,Variable,Expiration,DateTime,PropertyType,Mandatory

Note: The Variable has a DataType of Structure which is generic and must be assigned to a defined sub-type before it is transmitted on the wire. The generic Structure DataType results in an ExtensionObject being placed on the wire. The default defined sub-type is either ISA95TestResultDataType or ISA95TestResultMeasurementDataType depending on the nature of the data. If a different structure is used, it shall include all of the fields defined in this structure and the defined sub-type of this variable type shall also include any additional fields that are in the structure as separate variables.


            Id is an identifier of the Test Result. This field can be used to reference the actual result.


            ResultDescription is an additional information or description of the test result.


            TestDate is the date and time of the test. This Time is used to determine when a test expires, it is server specific as to whether it is a test start time or end time, but it should be consistent in all cases.


            Result is the result of the test (further defined in subtypes).


            ResultUnitOfMeasure is the unit of measure of the associated test result. It is defined as a structure to allow either a EUInformation or a measurement code (clause 6.3.8) to be reported.

Expiration is the date of the expiration of the test result.

7.6 ObjectType

7.6.1 Overview

The section defines common object types that are used by multiple section of the ISA specification (i.e. equipment and physical assets etc.) In some cases these types define a generic version of the object that will be further customized in the specific section, i.e. equipment or physical asset variable section.

The object types defined in the following sections make use of reference types that are defined in section 0. These reference types provide specific semantic information. To fully understand the Object models it may be required to review these reference descriptions.

7.6.2 ISA95ClassType

The ISA95ClassType is an abstract ObjectType that cannot be used directly. It is a subtype of BaseObjectType defined in OPC 10000-5. 

This abstract ObjectType is used to define groupings of functionality that is associated with an ISA95Object. AnyISA95Object may be associated with zero or more ISA95Classes. 

Objects of this ObjectType or its subtypes may be associated to ISA95TestSpecifications or their subtypes.

Table 45 - ISA95ClassType definition
Attribute,Value
BrowseName,ISA95ClassType
IsAbstract,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseObjectType defined in OPC 10000-5
,,,,,

7.6.3 ISA95ObjectType

The ISA95ObjectType is an abstract ObjectType that cannot be used directly. It is a subtype of BaseObjectType defined in OPC 10000-5. 

Table 46 - ISA95ObjectType definition
Attribute,Value
BrowseName,ISA95ObjectType
IsAbstract,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseObjectType defined in OPC 10000-5
,,,,,

7.6.4 ISA95TestSpecificationType

The ISA95TestSpecificationType is an abstract ObjectType that cannot be used directly. It is a subtype of BaseObjectType defined in OPC 10000-5. 

This ObjectType is a base ObjectType that has no elements that describe the test specification, it is expected that sub types of this ObjectType will be created by implementers of this standard and will define the details associated with a test specification. This ObjectType indicates the existence of a test specification. This is typically used where a test is required to ensure capability of a modelling target such as ISA95Person. 

Table 47 - ISA95TestSpecificationType definition
Attribute,Value
BrowseName,ISA95TestSpecificationType
IsAbstract,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseObjectType defined in OPC 10000-5
HasISA95Attribute,Variable,Version,String,BaseDataVariableType,


            Version is a version of the test specification.

8 ISA-95 Common Object Model

8.1 Personnel Information

8.1.1 Overview

The personnel model in ISA-95 is an abstract model that allows the definition of person and roles that individual persons can be assigned to PersonnelClasses (see Figure 22). The requirements associated with a given role may include specific training or certification. It may be related to Job Titles or skills. A single person may be associated with multiple roles. Persons may be grouped into a type of Person, to allow properties to be associated with all persons that fall into the given type. For example a Person Type of Operator type may allow, multiple operators to have the same defined qualification tests, some of which are defined by the operator role, others may be defined by safety role or a role for a specific type of equipment.

[Figure: Figure 22 - Personnel Overview]


            Figure 23 illustrates personnel model which consists of specific person, ISA95Classes of personnel, and qualification of personnel. It includes an example subtype that illustrates creating customized sub type of PersonnelClass. The illustration further illustrates creating actual instance of the individual types and how multiple classes can be combined into a single instance. This figure does not illustrate how a subtype of PersonType can be created and used to classify multiple persons as being of the same type. The concept of a sub type of PersonType is allowed, but since most persons would have unique training and classification in many cases subtypes of PersonType would not exist.

[Figure: Figure 23 - Personnel Information Model]

8.1.2 VariableTypes

8.1.2.1 QualificationTestResultType

The QualificationTestResultType is a concrete VariableType that can be used directly. It is a subtype of ISA95TestResultType VariableType defined in 7.5.4.

This VariableType indicates the results from a qualification test for a specific person. 

Table 48 - QualificationTestResultType definition
Attribute,Value
BrowseName,QualificationTestResultType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestResultTypeType defined in 7.5.4.

This variable type according to ISA-95 shall have prior and or multiple results available depending on the vendor specific model. To accommodate this requirement, vendors will be required to support historical storage of instances of QualificationTestResultType. 

8.1.2.2 PersonnelClassPropertyType

The PersonnelClassPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95ClassPropertyType defined in 7.5.4.

This VariableType indicates ISA95ClassProperties for ISA95PersonnelClass. Variables of this VariableType may be associated to the qualification test specification defined in 8.1.3.1. 

Table 49 - PersonnelClassPropertyType definition
Attribute,Value
BrowseName,PersonnelClassPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClasspropertyType defined in 7.5.2.
HasISA95ClassProperty,Variable,<PropertyName>,,PersonnelClassPropertyType,OptionalPlaceholder
TestedByQualificationTest,Object,<TestSpecification>,,QualificationTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible additional nested instances of PersonnelClassPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type PersonnelClassPropertyType or a subtype of it.


              <TestSpecification> is a placeholder for any test specification that this instance of a PersonnelClassPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByQualificationTest Reference and shall be of type QualificationTestSpecificationType or a subtype of it.

8.1.2.3 PersonPropertyType

The PersonPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95PropertyType defined in7.5.3.

This VariableType indicates ISA95Properties of a person. Person ISA95Property may be related to the qualification test specification defined in 8.1.3.1 and may be tested by the execution of the qualification test specification.

Table 50 - PersonPropertyType definition
Attribute,Value
BrowseName,PersonPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95PropertyType defined in 7.5.3.
HasTestResult,Variable,<TestResult>,BaseDataType,QualificationTestResultType,OptionalPlaceholder
HasISA95Property,Variable,<PropertyName>,,PersonPropertyType,OptionalPlaceholder
TestedByQualificationTest,Object,<TestSpecification>,,QualificationTestSpecificationType,OptionalPlaceholder


              <TestResult> is the results associated with qualification tests for this PersonPropertyType. These test results can have any name but shall be referenced using the HasTestResult Reference and shall be of type QualificationTestResultType or a subtype of it. In addition each <TestResult> shall have a ResultsForSpecification Reference to the instance of a QualificationTestSpecificationType that is associated to the given test result record. It is recommended that the names assigned to the object of QualificationTestSpecificationType and the <TestResult> variable follow some naming convention, to allow operators to more easily match test results to the test specification that they are for.


              <PropertyName> is a placeholder for possible additional nested instances of PersonPropertyType. These instances of PersonPropertyType can have any name but shall be referenced using the HasISA95Property reference and shall be of type PersonPropertyType or a subtype of it.


              <TestSpecification> is a placeholder for any test specification that this PersonPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByQualificationTest Reference and shall be of type QualificationTestSpecificationType or a subtype of it.

8.1.3 ObjectTypes

8.1.3.1 QualificationTestSpecificationType

The QualificationTestSpecificationType is a concrete ObjectType that can be used directly. It is a subtype of ISA95TestSpecificationType defined in7.6.4. 

This ObjectType indicates a qualification test specification. A qualification test specification may be associated with an ISA95PersonnelClass, an ISA95PersonnelClassProperty, an ISA95Person, or ISA95Person Property. This is typically used where a qualification test or ISA95Properly demonstrated competency is required to ensure that an ISA95Person has the correct training and/or experience for specific operations. A qualification test specification may test for one or more ISA95Properties.

Table 51 - QualificationTestSpecificationType definition
Attribute,Value
BrowseName,ISA95TestSpecificationType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestSpecificationType defined in 7.6.4.

8.1.3.2 PersonnelClassType

The PersonnelClassType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ClassType defined in7.6.2. 

This ObjectType indicates a grouping of persons with similar characteristics for a definite purpose such as manufacturing operations definition, scheduling, capability and performance. A subtype of PersonnelClassType may be associated to qualification test specification(s).

Table 52 - PersonnelClassType definition
Attribute,Value
BrowseName,PersonnelClassType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassType defined in 7.6.2.
HasISA95Class Property,Variable,<PropertyName>,BaseDataType,PersonnelClass PropertyType,OptionalPlaceholder
TestedByQualificationTest,Object,<TestSpecification>,,QualificationTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible additional nested PersonnelClasses. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type PersonnelClassPropertyType or a sub type of it

<TestSpecification> is a placeholder for any test specification that this PersonnelClass conforms to. These test specifications can have any name but shall be referenced using the TestedByQualificationTest Reference and shall be of type QualificationTestSpecificationType or a subtype of it

8.1.3.3 PersonType

The PersonType ObjectType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ObjectType ObjectType defined in7.6.3. 

This ObjectType indicates a specifically identified individual. A person may be tested by the execution of a qualification test specification.

Table 53 - PersonType definition
Attribute,Value
BrowseName,PersonType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ObjectType defined in 7.6.3.
HasISA95Property,Variable,<PropertyName>,BaseDataType,PersonPropertyType,OptionalPlaceholder
DefinedByPersonnelClass,Object,<PersonnelClass>,,PersonnelClassType,OptionalPlaceholder
TestedByQualificationTest,Object,<TestSpecification>,,QualificationTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for variable of PersonPropertyType. These Variables can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type PersonPropertyType or a sub type of it

<PersonnelClass> is a placeholder for Object classifications that are used to define this person.  These classifications can have any browse name but they shall be of PersonnelClassType and shall be referenced by DefinedByPersonnelClass ReferenceType 

<TestSpecification> is a placeholder for any test specification that this Person conforms to. These test specifications can have any name but shall be referenced using the TestedByQualificationTest Reference and shall be of type QualificationTestSpecificationType or a subtype of it

8.2 Role based Equipment Information

8.2.1 Overview

The ISA-95 Equipment Model is an abstract model that describes classes of logical equipment. The physical equipment is defined by physical assets. In the ISA-95 model, a logical device (equipment) usually does not change, but a physical device may change over time. For example a meter is being used, but it requires service, thus it is replaced by an identical meter. The Physical device gets changed, but in the logic of the system the equipment has not changed. The ISA-95 model further defines classes of equipment that define general functionality or features of a logical piece of equipment. These classes of equipment (EquipmentClassType) would be defined by an EquipmentClassType. Instances of these classes of Equipment are referenced by an EquipmentType, which is a definition of a logical piece of equipment. In a running system there would be multiple instances of the EquipmentType. There would also be multiple EquipmentClassTypes. Figure 24 provides an illustration of this concept. It is also acceptable to define subtypes of EquipmentType, where the associated EquipmentClassType never change and multiple instances of the subtype of EquipmentType exist.

[Figure: Figure 24 - Abstract Equipment Illustration]


            Figure 23 illustrates the Equipment Information model which consists of Equipment Types and EquipmentClassTypes. The illustration includes the definition of subtypes of EquipmentClassType, an instance of Equipment, and a subtype of EquipmentType. Any subtype of EquipmentType includes additional restrictions on Instance of the subtype such as the instance can never remove an associated EquipmentClassType.

[Figure: Figure 25 Equipment Information Model]

The role based equipment model contains information about specific equipment, equipment classes, equipment capability tests, and maintenance information associated with equipment. It can also contain information about related Physical Assets. The information about the related Physical Asset is represented as asset assignment information 

The asset assignment information would be part of the Equipment model as well as part of the Physical Asset model. The asset assignment information could be time series data and is accessed by standard Attribute Services as defined in OPC 10000-4.

The asset assignment information is represented as DataVariable that is part of the Equipment or Physical Asset. The DataType of the asset assignment VariableType is a structure that represents elements of the asset assignment information. This standard only defines basic information regarding the asset assignment. Third parties may create a subtype of this VariableType to represent third party specific information of an asset assignment. (See Figure 26)

[Figure: Figure 26 - Asset Assignment Information]

8.2.2 DataTypes

8.2.2.1 ISA95AssetAssignmentDataType

This structure contains elements that record the asset assignment. 

Table 54 - ISA95AssetAssignmentDataType Structure
Name,Type,Description
ISA95AssignemtDataType,Structure,Information that describes the asset assignment  record.
Id,NodeId,Identification that records the asset assignment.
AssignmentDescription,LocalizedText,Additional information or description about the assignment.
StartTime,DateTime,Starting time of the asset assignment.
EndTime,DateTime,Ending time of the asset assignment.

Its representation in the AddressSpace is defined in Table 55.

Table 55 - ISA95AssetAssignmentDataType Definition
Attributes,Value
BrowseName,ISA95AssetAssignmentDataType

8.2.3 VariableTypes

8.2.3.1 ISA95AssetAssignmentType

The ISA95AssetAssignmentType is a concrete VariableType that can be used directly. It is a subtype of BaseDataVariableType defined in OPC 10000-5. 

This VariableType is used to track the asset assignment, It is usually includes history. The Variables associated with VariableType provide the asset assignment information. The structure of asset assignment information can be extended. Therefore, third party may design particular structure for the asset assignment information. This standard defines the minimum information elements for the asset assignment.

Table 56 - ISA95AssetAssignmentType definition
Attribute,Value
BrowseName,ISA95AssetAssignmentType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5
HasISA95Attribute,Variable,Id,NodeId,PropertyType,Mandatory
HasISA95Attribute,Variable,AssignmentDescription,LocalizedText,PropertyType,Mandatory
HasISA95Attribute,Variable,StartTime,DateTime,PropertyType,Mandatory
HasISA95Attribute,Variable,StopTime,DateTime,PropertyType,Mandatory

This variable type according to ISA-95 shall maintain prior and/or support multiple results depending on the vendor specific information model. To accommodate this requirement, vendors will be required to support historical storage of the value for instances of ISA95AssetAssignmentType.

From history a user can determine all of the physical assets that were used to represent this logical piece of equipment. Also the history of all logical equipment a particular physical asset was assigned to can be reviewed, when this variable is used on a physical asset.


              Id is an identifier of the asset assignment information. This id is the NodeId of the instance of PhysicalAssetType that is currently assigned to this piece of equipment (if this variable is part of an Equipment object). This VariableType is also used for PhysicalAssetType objects, in which case this id would be the NodeId of the instance of the EquipmentType that the physical asset is assigned to. 


              AssignmentDescription is an additional information or description of the assignment.


              StartTime is the time at which the asset assignment was made.


              StopTime is the time at which the asset assignment was change / ended.

This standard defines ISA95AssetAssignmentDataType as the default DataType. Third parties may define their own structure that contains additional elements, but it must still contain all the elements defined in the ISA95AssetAssignmentDataType. It is also recommended that any new items that are added to the new ISA95AssetAssignmentDataType also be added to the new subtype of the ISA95AssetAssignmentType variable type. 

8.2.3.2 EquipmentCapabilityTestResultType

The EquipmentCapabilityTestResultType is a concrete VariableType that can be used directly. It is a subtype of ISA95TestResultType VariableType defined in 7.5.4.

This VariableType indicates the results from an Equipment test. 

Table 57 - EquipmentCapabilityTestResultType definition
Attribute,Value
BrowseName,EquipmentCapabilityTestResultType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestResultType defined in 7.5.4.

This variable type according to ISA-95 shall have prior and or multiple results available depending on the vendor specific model. To accommodate this requirement, vendors will be required to support historical storage of instances of EquipmentCapabilityTestResultType

8.2.3.3 EquipmentClassPropertyType

The EquipmentClassPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95ClassPropertyType defined in 7.5.4.

This VariableType indicates ISA95ClassProperties for an EquipmentClassType. Variables of this VariableType may be associated to an instance of an EquipmentCapabilityTestSpecificationType defined in 8.1.3.1. 

Table 58 - EquipmentClassPropertyType definition
Attribute,Value
BrowseName,EquipmentClassPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClasspropertyType defined in 7.5.2.
HasISA95ClassProperty,Variable,<PropertyName>,,EquipmentClassPropertyType,OptionalPlaceholder
TestedByEquipmentTest,Object,<TestSpecification>,,EquipmentCapabilityTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible nested instances of EquipmentClassPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type EquipmentClassPropertyType or a subtype of it


              <TestSpecification> is a placeholder for any test specification that this EquipmentClassPropertyType is tested by. These test specifications can have any name but shall be referenced using the TestedByEquipmentTest Reference and shall be of type EquipmentCapabilityTestSpecificationType or a subtype of it.

8.2.3.4 EquipmentPropertyType

The EquipmentPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95PropertyType defined in 7.5.3.

This VariableType indicates ISA95Properties of a role based equipment. An instance of an EquipmentPropertyType may be related to instances of EquipmentCapabilityTestSpecificationType defined in 8.1.3.1 and may be tested by the execution of the equipment test specification with results exchanged in an equipment test result.

Table 59 - EquipmentPropertyType definition
Attribute,Value
BrowseName,EquipmentPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95PropertyType defined in 7.5.3.
HasTestResult,Variable,<TestResult>,BaseDataType,EquipmentCapabilityTestResultType,OptionalPlaceholder
HasISA95Property,Variable,<PropertyName>,,EquipmentPropertyType,OptionalPlaceholder
TestedByEquipmentTest,Object,<TestSpecification>,,EquipmentCapabilityTestSpecificationType,OptionalPlaceholder


              <TestResult> is the optional results associated with an EquipmentCapabilityTestSpecificationType. These test results can have any name but shall be referenced using the HasTestResult Reference and shall be of type EquipmentCapabilityTestResultType or a subtype of it. In addition each <TestResult> shall have a ResultsForSpecification Reference to the instance of EquipmentCapabilityTestSpecificationType that it is associated with. It is recommended that the names assigned to the instance of the EquipmentCapabilityTestSpecificationType object and the <TestResult> variable follow some naming convention, to allow operators to more easily match test results to the test specification that they are for.


              <PropertyName> is a placeholder for possible additional nested instances of EquipmentPropertyTypes. These properties can have any name but shall be referenced using the HasISA95Property reference and shall be of type EquipmentPropertyType or a subtype of it


              <TestSpecification> is a placeholder for any capability test specification that an instance of this EquipmentPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByEquipmentTest Reference and shall be of type EquipmentCapabilityTestSpecificationType or a subtype of it

8.2.4 ObjectTypes

8.2.4.1 EquipmentCapabilityTestSpecificationType

The EquipmentCapabilityTestSpecificationType is a concrete ObjectType that can be used directly. It is a subtype of ISA95TestSpecificationType defined in 7.6.4. 

This ObjectType indicates an equipment capability test. An equipment capability test may be associated with an EquipmentClassType and an instance of an EquipmentClassPropertyType, an instance of EquipmentType or an instance of EquipmentPropertyType. This is typically used where a test is required to ensure that the equipment has the necessary capability and capacity. An instance of an EquipmentCapabilityTestSpecificationType may be associated with more than one EquipmentClassType and also to more than one instance of an EquipmentType and also to more than one subtype of an EquipmentType.

Table 60 - EquipmentCapabilityTestSpecificationType
Attribute,Value
BrowseName,EquipmentCapabilityTestSpecificationType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestSpecificationType defined in 7.6.4.

8.2.4.2 EquipmentClassType

The EquipmentClassType is an abstract ObjectType; it is expected to be subtyped. It is a subtype of ISA95ClassType defined in 7.6.2. 

This ObjectType indicates a grouping of equipment with similar characteristics for a definite purpose such as manufacturing operations definition, scheduling, capability and performance. The EquipmentClassType may be associated to objects of an EquipmentCapabilityTestSpecificationType. It is expected that subtypes of the EquipmentClassType will be created that represent a particular class of equipment. These subtypes will have their own set of instance of EquipmentClassPropertyType and EquipmentCapabilityTestSpecificationType.

Table 61 - EquipmentClassType definition
Attribute,Value
BrowseName,EquipmentClassType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassType defined in 7.6.2.
HasISA95Class Property,Variable,<PropertyName>,BaseDataType,EquipmentClassPropertyType,OptionalPlaceholder
TestedByEquipmentTest,Object,<TestSpecification>,,EquipmentCapabilityTestSpecificationType,OptionalPlaceholder
HasISA95Attribute,Variable,EquipmentLevel,ISA95EquipmentElementLevelEnum,PropertyType,Optional


              <PropertyName> is a placeholder for possible additional nested instances of EquipmentClassPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type EquipmentClassPropertyType or a subtype of it


              <TestSpecification> is a placeholder for any capability test specification that this EquipmentClassType conforms to. These capability test specifications can have any name but shall be referenced using the TestedByEquipmentTest Reference and shall be of type EquipmentCapabilityTestSpecificationType or a subtype of it


              EquipmentLevel is an identification of the level in the role based equipment hierarchy.

8.2.4.3 EquipmentType

The EquipmentType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ObjectType defined in 6.7.2.

This ObjectType defines a piece of equipment. Equipment may be tested by the execution of one or more tests defined by EquipmentCapabilityTestSpecificationType. Individual instance of this EquipmentType would have one or more reference(s) to EquipmentClassType(s) that the instance of the EquipmentType is defined by. A subtype of EquipmentType may also be defined for a fixed set of referenced EquipmentClassTypes. By definition of the ISA-95 model, when an Equipment instance or a sub type of EquipmentType references an EquipmentClassType, the addition of said reference results in the addition of all instances of EquipmentClassPropertyType defined for the referenced EquipmentClassType to the Equipment instance (or EquipmentType subtype) as instances of EquipmentPropertyType. These instances of EquipmentPropertyType will have all the same Attributes and Properties as the corresponding EquipmentClassPropertyType instance. This includes the same value for the BrowseName, DisplayName, Description and any other properties.

 This ObjectType may be further subtyped. The subtypes create some additional restrictions. Any EquipmentClassType references that are added to a subtype of an EquipmentType cannot be removed from an instance of the subtype. If the EquipmentType subtype is updated then all instance of the EquipmentType subtype must also be updated. For example if an additional EquipmentClassType is added to the EquipmentType subtype that that EquipmentClassType must be added to all instances of the EquipmentType subtype. This allows for creating a single EquipmentType that is used for multiple EquipmentType instances.

Equipment may be made of other equipment.

Table 62 - EquipmentType definition
Attribute,Value
BrowseName,EquipmentType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ObjectType defined in 7.6.3.
HasISA95Property,Variable,<PropertyName>,BaseDataType,EquipmentPropertyType,OptionalPlaceholder
DefinedByEquipmentClass,Object,<EquipmentClass>,,EquipmentClassType,OptionalPlaceholder
TestedByEquipmentTest,Object,<TestSpecification>,,EquipmentCapabilityTestSpecificationType,OptionalPlaceholder
MadeUpOfEquipment,Object,<Equipment>,,EquipmentType,OptionalPlaceholder
HasISA95Attribute,Variable,EquipmentLevel,ISA95EquipmentElementLevelEnum,PropertyType,Optional
ImplementedBy,Object,PhysicalAsset,,PhysicalAssetType,Optional
HasComponent,Variable,AssetAssignment,structure,ISA95AssetAssignmentType,Optional


              <PropertyName> is a placeholder for possible additional instances of EquipmentPropertyType. These properties can have any name but shall be referenced using the HasISA95Property reference and shall be of type EquipmentPropertyType or a subtype of it

<EquipmentClass> is a placeholder for possible related EquipmentClassTypes These EquipmentClassTypes can have any name but shall be referenced using the DefinedByEquipmentClass reference and shall be an EquipmentClassType or a subtype of it


              <TestSpecification> is a placeholder for any capability test specification that instances of this EquipmentType conform to. These test specifications can have any name but shall be referenced using the TestedByEquipmentTest Reference and shall be of type EquipmentCapabilityTestSpecificationType or a subtype of it

<Equipment> is a placeholder for sub instances of EquipmentType. These instances of EquipmentType can have any name but shall be referenced using the MadeUpOfEquipment reference and shall be an instance of EquipmentType or a subtype of it


              EquipmentLevel is an identification of the level in the role based equipment hierarchy.

PhysicalAsset is an instance of a PhysicalAssetType that is assigned to this instance of an EquipmentType.

AssetAssignment - Is used to track the history of the physical assets assigned to this logical equipment.

8.3 Physical Asset information

8.3.1 Overview

The ISA-95 Physical Asset Model includes defining the class of physical devices that exist in a system as well as the actual physical devices. These definitions include manufacturing related information for classes of devices and actual vendor related information for instances of physical devices. Figure 27 illustrate this abstract model and the relationships that are modelled in the OPC UA Information model. For a description of the relationship between physical assets and equipment see section 8.2.1.

[Figure: Figure 27 - Manufacturers and Vendors in Physical Asset Information]

Physical Assets can be composed of other Physical Assets. Physical Asset classes describe a general classification of an asset, which may be supplied by multiple vendors, each with unique model numbers. Vendors may have additional information associated with them. Individual instance of a particular Physical Asset would have a serial number that is provided by the vendor that supplied the device. 


            Figure 28 illustrates Physical Asset Information Model in terms of the OPC UA Information Model. This model illustrates the base Physical Asset model. It further provides an example set of possible subtypes of PhysicalAssetClassTypes and instances of Physical Assets.

[Figure: Figure 28 - Physical Asset Information Model]

8.3.2 VariableTypes

8.3.2.1 CompanyType

The CompanyType is a concrete VariableType that can be used directly. It is a subtype of BaseDataVariableType defined in OPC 10000-5

This VariableType is used to provide details regarding company information for PhysicalAssetClassTypes or for instances of PhysicalAssetType. In most instances this type will be further subtyped to provide additional information regarding the company. The ISA-95 specification does not define a structure or set of fields for company information. Some systems will provide a list of additional information, such as address, contact and other details. Other system may simply provide a link or reference to some other system that provides the detailed company information. In later sections, this specification will provide a TypicalCompanyType (see D.3) that can be used as a default if no other linked system exists. This type could also be further subtyped as needed.

Table 63 - CompanyType Type definition
Attribute,Value
BrowseName,CompanyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5.
,,,,,

8.3.2.2 GeoSpatialLocationType

The GeoSpatialLocationType is a concrete VariableType that can be used directly. It is a subtype of PropertyType defined in OPC 10000-3

This VariableType is used to provide details regarding Physical Location information for PhysicalAssetClassType

Table 64 - GeoSpatialLocationType Type definition
Attribute,Value
BrowseName,GeoSpatialLocationType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,String
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the PropertyType defined in OPC 10000-5.
,,,,,

8.3.2.3 PhysicalAssetCapabilityTestResultType

The PhysicalAssetCapabilityTestResultType is a concrete VariableType that can be used directly. It is a subtype of ISA95TestResultType defined in 7.5.4.

This VariableType indicates the results from a physical asset capability test for a specific physical asset. 

Table 65 - PhysicalAssetCapabilityTestResultType definition
Attribute,Value
BrowseName,PhysicalAssetCapabilityTestResultType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestResultType defined in 7.5.4.

This variable type according to ISA-95 shall have prior and or multiple results available depending on the vendor specific model. To accommodate this requirement, vendors will be required to support historical storage of instances of PhysicalAssetCapabilityTestResultType. 

8.3.2.4 PhysicalAssetClassPropertyType

The PhysicalAssetClassPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95ClassPropertyType defined in 7.5.4.

This VariableType indicates ISA95ClassProperties for a PhysicalAssetClassType. Variables of this VariableType may be associated with tests defined by PhysicalAssetCapabilityTestSpecificationType defined in 8.3.3.1. 

Table 66 - PhysicalAssetClassPropertyType definition
Attribute,Value
BrowseName,PhysicalAssetClassPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClasspropertyType defined in 7.5.2.
HasISA95ClassProperty,Variable,<PropertyName>,,PhysicalAssetClassPropertyType,OptionalPlaceholder
TestedByPhysicalAssetTest,Object,<TestSpecification>,,PhysicalAssetCapabilityTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible additional nested instances of PhysicalAssetClassPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type PhysicalAssetClassPropertyType or a subtype of it


              <TestSpecification> is a placeholder for any test specification that an instance of this PhysicalAssetClassPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByPhysicalAssetTest Reference and shall be of type PhysicalAssetCapabilityTestSpecificationType or a subtype of it.

8.3.2.5 PhysicalAssetPropertyType

The PhysicalAssetPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95PropertyType defined in7.5.3.

This VariableType indicates ISA95Properties of a role based equipment. Variables of this type may be related to tests defined by PhysicalAssetCapabilityTestSpecificationType defined in 8.3.3.1 and have Test results associated with them.

Table 67 - PhysicalAssetPropertyType definition
Attribute,Value
BrowseName,PhysicalAssetPropertyType
IsAbstract,False
ValueRank,0
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95PropertyType defined in 7.5.3.
HasTestResult,Variable,<TestResult>,BaseDataType,PhysicalAssetCapabilityTestResultType,OptionalPlaceholder
HasISA95Property,Variable,<PropertyName>,,PhysicalAssetPropertyType,OptionalPlaceholder
TestedByPhysicalAssetTest,Object,<TestSpecification>,,PhysicalAssetCapabilityTestSpecificationType,OptionalPlaceholder


              <TestResult> is the optional results associated with an instance of PhysicalAssetCapability-TestSpecificationType These test results can have any name but shall be referenced using the HasTestResult Reference and shall be of type PhysicalAssetCapabilityTestResultType or a subtype of it. In addition each <TestResult> shall have a ResultsForSpecification Reference to the instance of the PhysicalAssetCapabilityTestSpecificationType that is associated to the given test result record. It is recommended that the names assigned to the <TestSpecification> and the <TestResult> variable follow some naming convention, to allow operators to more easily match test results to the test specification that they are for.


              <PropertyName> is a placeholder for possible additional instances of PhysicalAssetPropertyTypes. These properties can have any name but shall be referenced using the HasISA95Property reference and shall be of type PhysicalAssetPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any capability test specification that an instance of this PhysicalAssetPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByPhysicalAssetTest Reference and shall be of type PhysicalAssetCapabilityTestSpecificationType or a sub type of it

8.3.3 ObjectTypes

8.3.3.1 PhysicalAssetCapabilityTestSpecificationType

The PhysicalAssetCapabilityTestSpecificationType is a concrete ObjectType that can be used directly. It is a subtype of ISA95TestSpecificationType defined in 6.7.3. 

This ObjectType indicates a test for a physical asset. An instance of a PhysicalAssetCapabilityTestSpecificationType may be associated with a PhysicalAssetClassType, instances of PhysicalAssetClassPropertyType, instance of PhysicalAssetType or instances of PhysicalAssetPropertyType. This is typically used where a test is required to ensure that the Physical Asset has the necessary capability and capacity. An instance of a PhysicalAssetCapabilityTestSpecificationType may be associated with multiple instances of Physical Assets and/or multiple PhysicalAssetClassTypes. 

Attribute,Value
BrowseName,PhysicalAssetCapabilityTestSpecificationType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestSpecificationType defined in 7.6.4.

8.3.3.2 PhysicalAssetClassType

The PhysicalAssetClassType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ClassType defined in 6.7.1. 

This ObjectType indicates a grouping of Physical Assets with similar characteristics for a definite purpose such as manufacturing operations definition, scheduling, capability and performance. An Object of PhysicalAssetClassType may be associated with an instance of a PhysicalAssetCapabilityTestSpecificationType. It is expected that subtypes of the PhysicalAssetClassType will be created that represent a particular class of physical asset. These subtypes will have their own set of instances of PhysicalAssetClassPropertyTypes and PhysicalAssetCapabilityTestSpecificationTypes

Table 68 - PhysicalAssetClassType definition
Attribute,Value
BrowseName,PhysicalAssetClassType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassType defined in 7.6.2.
HasISA95ClassProperty,Variable,<PropertyName>,BaseDataType,PhysicalAssetClassPropertyType,OptionalPlaceholder
HasISA95Attribute,Variable,Manufacturer,,CompanyType,Optional
HasISA95Attribute,Variable,ModelNumber,String,BaseDataVariableType,Optional
TestedByPhysicalAssetTest,Object,<TestSpecification>,,PhysicalAssetCapabilityTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible additional instances of PhysicalAssetClass-PropertyType. These properties can have any name but shall be referenced using the HasISA95Property reference and shall be of type PhysicalAssetClassPropertyType or a sub type of it.


              Manufacturer is the Manufacturer of this PhysicalAssetClassType. The Manufacture shall be referenced using the HasISA95Attribute reference and shall be of type CompanyType or a sub type of it. 


              ModelNumber is the Manufacture's ModelNumber that could be associated with this PhysicalAssetClassType. The ModelNumber is referenced using the HasISA95Attribute reference type and shall be a string of type BaseDataVariableType or a sub type of it.


              <TestSpecification> is a placeholder for any capability test specification that this PhysicalAssetClassType conforms to. These test specifications can have any name but shall be referenced using the TestedByPhysicalAssetTest Reference and shall be of type PhysicalAssetCapabilityTestSpecificationType or a sub type of it

8.3.3.3 PhysicalAssetType

The PhysicalAssetType ObjectType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ObjectType defined in 6.7.2. Individual instance of this PhysicalAssetType would have reference to PhysicalAssetClassType that the instance of the PhysicalAssetType supports. By definition of the ISA-95 model, when a Physical Asset instance or PhysicalAssetType references a PhysicalAssetClassType, the addition of said reference results in the addition of all instance of PhysicalAssetClassPropertyType defined for the referenced PhysicalAssetClassType to be added to the Physical Asset instance (or PhysicalAssetType subtype) as instances of PhysicalAssetPropertyType. These ISA95Properties will have all the same Attributes and Properties as the corresponding PhysicalAssetClassPropertyType instance.

This ObjectType may be further subtyped. The subtypes create some additional restrictions. Any PhysicalAssetClassType references that are added to a subtype of a PhysicalAssetType cannot be removed from instance of the subtype. If the PhysicalAssetType subtype is updated than all instance of the PhysicalAssetType must also be updated. For example if an additional PhysicalAssetClassType is added to the PhysicalAssetType subtype than that PhysicalAssetClassType must be added to all instances of the PhysicalAssetType subtype. This allows for creating a single PhysicalAssetType that is used for multiple physical asset instances.

This ObjectType indicates a specific physical asset. A physical asset may be tested by the execution of an instance of a PhysicalAssetCapabilityTestSpecificationType.

A PhysicalAssetType may be made of instances of PhysicalAssetType.

Table 69 - PhysicalAssetType definition
Attribute,Value
BrowseName,PhysicalAssetType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ObjectType defined in 7.6.3.
HasISA95Property,Variable,<PropertyName>,BaseDataType,PhysicalAssetPropertyType,OptionalPlaceholder
MadeUpOfPhysicalAsset,Object,<PhysicalAsset>,,PhysicalAssetType,OptionalPlaceholder
DefinedByPhysicalAssetClass,Object,PhysicalAssetClass,,PhysicalAssetClassType,Optional
LocatedIn,Variables,PhysicalLocation,String,GeoSpatialLocationType,Optional
HasISA95Attribute,Variables,FixedAssetId,CDTIdentifier,BaseDataVariableType,Optional
HasISA95Attribute,Variables,VendorId,BaseDataType,CompanyType,Optional
TestedByPhysicalAssetTest,Object,<TestSpecification>,,PhysicalAssetCapabilityTestSpecificationType,OptionalPlaceholder
ImplementationOf,Object,Equipment,,EquipmentType,Optional
HasComponent,Variable,AssetAssignment,structure,ISA95AssetAssignmentType,Optional


              <PropertyName> is a placeholder for possible instances of PhysicalAssetPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type PhysicalAssetPropertyType or a subtype of it

<PhysicalAsset> is a placeholder for instance of PhysicalAssetType that this instance of PhysicalAssetType may be made up of. .These Objects can have any name but shall be referenced using the MadeUpOfPhysicalAsset reference and shall be to PhysicalAssetType or a subtype of it

PhysicalAssetClass defines the functionality of an instance of this PhysicalAssetType. .This Object shall be referenced using the DefinedByPhysicalAssetClass reference and shall be to PhysicalAssetClassType or a subtype of it


              PhysicalLocation is the actual location associated with the instance of this PhysicalAssetType


              FixedAssetId is the vendor provided identification number provided with the instance of the PhysicalAssetType. For Example it maybe the serial number associated with device.


              VendorId is the vendor that provides the instance of this PhysicalAssetType. This may be the same as the manufacturer associated with the related class, but it may also be different. For example a system integrator maybe the vendor that provides the PhysicalAssetType, even though it is manufactured by another company.


              <TestSpecification> is a placeholder for any capability test specification that an instance of this PhysicalAssetType conforms to. These test specifications can have any name but shall be referenced using the TestedByPhysicalAssetTest Reference and shall be of type PhysicalAssetCapabilityTestSpecificationType or a subtype of it

Equipment is the Equipment assigned to the instance of the PhysicalAssetType.

AssetAssignment - Is used to track the history of the logical Equipment to which this Physical Asset was assigned.

8.4 Material information

8.4.1 Overview

 Figure 29 provides an overview of the ISA-95 Material handling information model

[Figure: Figure 29 - Material Information Abstract Illustration]

Material handling includes the definition of a class of material; this class can include material definitions that further define what the material is. These classes of materials are applied to groupings of the actual materials (lots). In many cases these groupings are further broken down into sub-groupings (sub-lots).


            Figure 23 illustrates the material model which consists of material lots, material sub-lots, material classes, material definitions, and material test specifications.

Typically a class of materials is created and further subtyped into MaterialDefinitionType. These MaterialDefinitionTypes are usually vendor specific versions of the MaterialClassType. From these MaterialDefinitionTypes instances of MaterialLotType or subtypes of MaterialLotType are dynamically created. These instances of a MaterialLotType are maintained in the system for some period of time and then they are removed. For example, a technician may scan a barcode on a just delivered pallet of chemicals; this would cause an instance of the MaterialLotType to be created. This instance of a MaterialLotType may be composed of instances of MaterialSublotType (individual drums of that make up the pallet). When the last drum of chemical used up and all products that were created using the chemicals have been delivered, the system may delete the instance of the MaterialLotType that had automatically been created. In some cases sub types of MaterialLotType may be created, allowing for easier dynamic creation of an instance of a MaterialLotType that is assembled from specific MaterialSublotType(s) 

A MaterialDefinitionType defines a specific type of material from a specific supplier. This corresponds to an entry in a corporate Material Master database. For example, it may be stainless steel wire from supplier Ajax Steel, with certain properties, such as hardness and carbon content. A MaterialClassType is a specific type of material without specifying the source of the material. For example, it may be stainless steel wire, with a range of hardness and range of carbon content. The MaterialClassType is used when you don't care where the material comes from, such as "use any old stainless steel wire". The MaterialDefinitionType is used when you do care where the material comes from, such as "Ajax Steel stainless steel wire". Both types are often used in data exchanges.

In many systems the actual instances of MaterialLotType may exist in a database and be referenced by the OPC UA Server (i.e. they may not exist in memory in the OPC UA Server, but the Server would know how to access them and know what instances are available). If a client needs to modify an instance of a MaterialLotType (i.e. change the quantity or some other setting), the Server would handle the update to the underlining database.  

[Figure: Figure 30 - Material Information Model]

8.4.2 VariableTypes

8.4.2.1 MaterialTestResultType

The MaterialTestResultType is a concrete VariableType that can be used directly. It is a subtype of ISA95TestResultType defined in 7.5.4.This VariableType indicates the results from executing an instance of a MaterialTestSpecificationType for a specific MaterialLotType. 

Table 70 - MaterialTestResultType definition
Attribute,Value
BrowseName,MaterialTestResultType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,Structure
Historizing,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestResultType defined in 7.5.4.

This variable type according to ISA-95 shall have prior and or multiple results available depending on the vendor specific model. To accommodate this requirement, vendors will be required to support historical storage of instances of MaterialTestResultType. 

8.4.2.2 MaterialDefinitionPropertyType

The MaterialDefinitionPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95ClassPropertyType defined in 7.5.4.

This VariableType indicates ISA95ClassProperties for MaterialDefinitionTypes. Variables of this VariableType may be associated to an instance of a MaterialTestSpecificationType defined in 8.4.3.1. 

Table 71 - MaterialDefinitionPropertyType definition
Attribute,Value
BrowseName,MaterialDefinitionPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassPropertyType defined in 7.5.2.
HasISA95ClassProperty,Variable,<PropertyName>,,MaterialDefinitionPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible instances of MaterialDefinitionPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type MaterialDefinitionPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that this MaterialDefinitionPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a sub type of it.

8.4.2.3 MaterialClassPropertyType

The MaterialClassPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95ClassPropertyType defined in 7.5.4.

This VariableType indicates ISA95ClassProperties for MaterialClassTypes. Variables of this VariableType may be associated to an instance of a MaterialTestSpecificationType defined in 8.4.3.1 

Table 72 - MaterialClassPropertyType definition
Attribute,Value
BrowseName,MaterialClassPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClasspropertyType defined in 7.5.2.
HasISA95ClassProperty,Variable,<PropertyName>,,MaterialClassPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder


              <PropertyName> is a placeholder for possible instances of MaterialClassPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type MaterialClassPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specifications that this MaterialClassPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a sub type of it.

8.4.2.4 MaterialLotPropertyType

The MaterialLotPropertyType is a concrete VariableType that can be used directly. It is a subtype of ISA95PropertyType defined in7.5.3.

This VariableType indicates ISA95Properties of a MaterialLotType. A MaterialLotPropertyType may be associated to an instance of a MaterialTestSpecificationType defined in 8.4.3.1. An instance of a MaterialLotPropertyType may be tested by the execution of an instance of the MaterialTestSpecificationType.

Table 73 - MaterialLotPropertyType definition
Attribute,Value
BrowseName,MaterialLotPropertyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95PropertyType defined in 7.5.3.
HasTestResult,Variable,<TestResult>,BaseDataType,MaterialTestResultType,OptionalPlaceholder
HasISA95Property,Variable,<PropertyName>,,MaterialLotPropertyType,OptionalPlaceholder
TestedBy Material Test,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder


              <TestResult> is a placeholder for possible material test results. These test results can have any name but shall be referenced using the HasTestResult Reference and shall be of type MaterialTestResultType or a subtype of it. In addition each <TestResult> shall have a ResultsForSpecification Reference to the instance of the MaterialTestSpecificationType that is associated to the given test result record. It is recommended that the names assigned to the instance of a MaterialTestSpecificationType and the <TestResult> variable follow some naming convention, to allow operators to more easily match test results to the test specification that they are for.


              <PropertyName> is a placeholder for possible instance of MaterialLotPropertyType. These properties can have any name but shall be referenced using the HasISA95Property Reference and shall be of type MaterialLotPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that an instance of this MaterialLotPropertyType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a sub type of it.

8.4.3 Objects

8.4.3.1 MaterialTestSpecificationType

The MaterialTestSpecificationType is a concrete ObjectType that can be used directly. It is a subtype of ISA95TestSpecificationType defined in 7.6.4. 

This ObjectType indicates a material test specification. A material test specification may be associated with a MaterialDefinitionType, an instance of a MaterialDefinitionPropertyType, a MaterialClassType, an instance of a MaterialClassPropertyType, an instance of a MaterialLotType, an instance of a MaterialLotPropertyType or an instance of a MaterialSublotType. This is typically used to specify a material test specification to determine a value for a property. An instance of a MaterialTestSpecificationType may test one or more of these items.

Table 74 - MaterialTestSpecificationType definition
Attribute,Value
BrowseName,MaterialTestSpecificationType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95TestSpecificationType defined in 7.6.4.

8.4.3.2 MaterialClassType

The MaterialClassType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ClassType defined in 7.6.2. 

This ObjectType indicates a grouping of material classes with similar characteristics for a definite purpose such as manufacturing operations definition, scheduling, capability and performance. An Object of MaterialClassType may be associated to material test specification(s).

Table 75 - MaterialClassType definition
Attribute,Value
BrowseName,MaterialClassType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassType defined in 7.6.2.
HasISA95ClassProperty,Variable,<PropertyName>,BaseDataType,MaterialClassPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder
AssembledFrom Class,Object,<AssemblyClass>,,MaterialClassType,OptionalPlaceholder
HasISA95Attribute,Variable,AssemblyType,BaseDataType,BaseDataVariableType,Optional
HasISA95Attribute,Variable,AssemblyRelationship,BaseDataType,BaseDataVariableType,Optional


              <PropertyName> is a placeholder for instances of MaterialClassPropertyType that further define this MaterialClassType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type MaterialClassPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that this MaterialClassType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a subtype of it

<AssemblyClass> is a placeholder for any MaterialClassTypes that are used to compose this material. These MaterialClassTypes (assemblies) can have any name, but they shall be referenced using the AssembledFromClass reference and shall be of type MaterialClassType. 

AssemblyType is flag that indicates if this assembly is a physical or logical assembly. This property is optional on a MaterialClassType, in that it is only on MaterialClassTypes that are being used as an assembly, but it is required on an assembly.

AssemblyRelationship is flag that indicates if this assembly is permanent or transient. This property is optional on a MaterialClassTypes, in that it is only on MaterialClassTypes that are being used as an assembly, but it is required on an assembly.

8.4.3.3 MaterialDefinitionType

The MaterialDefinitionType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ClassType defined in 7.6.2

This ObjectType indicates a grouping of Material with similar characteristics for a definite purpose such as manufacturing operations definition, scheduling, capability and performance. A MaterialDefinitionType may be associated to material test specification(s). MaterialDefinitionType is used to further classify a MaterialClassType, for example a MaterialClassType may be Hydrochloric Acid, a MaterialDefinitionType may be ABC Chemicals version of Hydrochloric Acid, with addition properties provided by the company.

Table 76 - MaterialDefinitionType definition
Attribute,Value
BrowseName,MaterialDefinitionType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ClassType defined in 7.6.2.
HasISA95ClassProperty,Variable,<PropertyName>,BaseDataType,MaterialDefinitionPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder
DefinedByMaterialClass,Object,<MaterialClass>,,MaterialClassType,OptionalPlaceholder
AssembledFrom Definition,Object,<AssemblyDefinition>,,MaterialDefinitionType,OptionalPlaceholder
HasISA95Attribute,Variable,AssemblyType,BaseDataType,BaseDataVariableType,Optional
HasISA95Attribute,Variable,AssemblyRelationship,BaseDataType,BaseDataVariableType,Optional


              <PropertyName> is a placeholder for possible instances of MaterialDefinitionPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type MaterialDefinitionPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that this MaterialDefinitionType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a subtype of it.


              <MaterialClass> is a placeholder for any material class that defines this MaterialDefinitionType  These material classes can have any name but shall be referenced using the DefinedByMaterialClass Reference and shall be  MaterialClassType or a subtype of it.

<AssemblyDefinition> is a placeholder for any MaterialDefinitionTypes that are used to compose this material. These MaterialDefinitionType (assemblies) can have any name, but they shall be referenced using the AssembledFromDefinition reference and shall be subtypes of MaterialDefinitionType. 

AssemblyType is flag that indicates if this assembly is a physical or logical assembly. This property is optional on a MaterialDefinitionType, in that it is only on MaterialDefinitionTypes that are being used as an assembly but it required on a MaterialDefinitionType that is an assembly.

AssemblyRelationship is flag that indicates if this assembly is permanent or transient. This property is optional on a MaterialDefinitionType, in that it is only on MaterialDefinitionTypes that are being used as an assembly but it required on a MaterialDefinitionType that is an assembly.

8.4.3.4 MaterialLotType

The MaterialLotType ObjectType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ObjectType defined in7.6.3. 

This ObjectType indicates a specifically identified material lot. An instance of a MaterialLotType may be tested by the execution of a material test specification. 

Individual instances of this MaterialLotType would have a reference to MaterialClassType(s) that the instance of the MaterialLotType supports. By definition of the ISA-95 model, when MaterialLotType references a MaterialClassType, the addition of said reference results in the addition of all instances of MaterialClassPropertyType defined for the referenced MaterialClassType to be added to the MaterialLotType (or MaterialLotType subtype) as instances of MaterialLotPropertyType. These ISA95Properties will have all the same Attributes and Properties as the corresponding MaterialClassPropertyType instance.

 This ObjectType may be further subtyped. The subtypes create some additional restrictions. Any MaterialClassType references that are added to a subtype of a MaterialLotType cannot be removed from instance of the subtype. If the MaterialLotType subtype is updated than all instance of the MaterialLotType must also be updated. For example if an additional Instance of a MaterialLotPropertyType is added to the MaterialLotType subtype than that instance of MaterialLotPropertyType must be added to all instances of the MaterialLotType subtype. This allows for creating a single MaterialLotType that is used for multiple material lot instances.

Table 77 - MaterialLotType definition
Attribute,Value
BrowseName,MaterialLotType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ObjectType defined in 7.6.3.
HasISA95Property,Variable,<PropertyName>,BaseDataType,MaterialLotPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder
AssembledFromLot,Object,<AssemblyLot>,,MaterialLotType,OptionalPlaceholder
AssembledFromSublot,Object,<AssemblySubLot>,,MaterialSublotType,OptionalPlaceholder
HasISA95Attribute,Variable,AssemblyType,BaseDataType,BaseDataVariableType,Optional
HasISA95Attribute,Variable,AssemblyRelationship,BaseDataType,BaseDataVariableType,Optional
MadeUpOfMaterialSublot,Object,<Sublot>,,MaterialSublotType,OptionalPlaceholder
DefinedByMaterialDefinition,Object,MaterialDefinition,,MaterialDefinitionType,Optional
HasISA95Attribute,Variable,Status,CDTIdentifier,BaseDataVariableType,Optional
HasISA95Attribute,Variable,StorageLocation,CDTIdentifier,BaseDataVariableType,Optional
HasISA95Attribute,Variable,Quantity,BaseDataType,BaseDataVariableType,Optional
,,,,,


              <PropertyName> is a placeholder for instances of MaterialLotPropertyType. These properties can have any name but shall be referenced using the HasISA95ClassProperty reference and shall be of type MaterialLotPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that this MaterialLotType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a subtype of it

<AssemblyLot> is a placeholder for any Material Lots that are used to compose this material. These MaterialLotType assemblies can have any name, but they shall be referenced using the AssembledFromLot reference and shall be of type MaterialLotType. 

<AssemblySubLot> is a placeholder for any Material Sub Lots that are used to compose this material. These MaterialSublotType assemblies can have any name, but they shall be referenced using the AssembledFromSublot reference and shall be of type MaterialSublotType. 

AssemblyType is flag that indicates if this assembly is a physical or logical assembly. This property is optional on a MaterialLotType, in that it is only on instances of MaterialLotTypes that are being used as an assembly.

AssemblyRelationship is flag that indicates if this assembly is permanent or transient. This property is optional on a MaterialLotType, in that it is only on Instances of MaterialLotTypes that are being used as an assembly.

<Sublot> is a placeholder for any Instance of MaterialSublotTypes that are used to compose this material. These instances of MaterialSublotTypes can have any name, but they shall be referenced using the MadeUpOf reference and shall be of type MaterialSublotType or one of its subtypes.

MaterialDefinition is a material definition that is associated to this instance of MaterialLotType.

Status provides optional status information.

StorageLocation is the optional identification of the physical location of the material lot.

Quantity is the amount of material in this lot. 

8.4.3.5 MaterialSublotType

The MaterialSublotType is a concrete ObjectType that can be used directly. It is a subtype of ISA95ObjectType defined in7.6.3. 

This ObjectType indicates a specifically identified material Sublot. An instance of a MaterialSublotType may be tested by the execution of an instance of a MaterialTestSpecificationType. Instance of MaterialSublotType behave in the same manner as instances of MaterialLotType with regard to MaterialClassType definitions.

Table 78 - MaterialSublotType definition
Attribute,Value
BrowseName,MaterialSublotType
IsAbstract,False
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the ISA95ObjectType defined in 7.6.3.
HasISA95Property,Variable,<PropertyName>,BaseDataType,MaterialLotPropertyType,OptionalPlaceholder
TestedByMaterialTest,Object,<TestSpecification>,,MaterialTestSpecificationType,OptionalPlaceholder
AssembledFromLot,Object,<AssemblyLot>,,MaterialLotType,OptionalPlaceholder
AssembledFromSublot,Object,<AssemblySubLot>,,MaterialSublotType,OptionalPlaceholder
HasISA95Attribute,Variable,AssemblyType,BaseDataType,BaseDataType,Optional
HasISA95Attribute,Variable,AssemblyRelationship,BaseDataType,BaseDataType,Optional
MadeUpOfMaterialSublot,Object,<Sublot>,,MaterialSublotType,OptionalPlaceholder
DefinedByMaterialDefinition,Object,MaterialDefinition,,MaterialDefinitionType,Optional
HasISA95Attribute,Variable,Status,CDTIdentifier,BaseDataVariableType,Optional
HasISA95Attribute,Variable,StorageLocation,CDTIdentifier,BaseDataVariableType,Optional
HasISA95Attribute,Variable,Quantity,BaseDataType,BaseDataVariableType,Optional


              <PropertyName> is a placeholder for instance of MaterialLotPropertyType. These properties can have any name but shall be referenced using the HasISA95Property reference and shall be of type MaterialLotPropertyType or a sub type of it


              <TestSpecification> is a placeholder for any test specification that this instance of MaterialSublotType conforms to. These test specifications can have any name but shall be referenced using the TestedByMaterialTest Reference and shall be of type MaterialTestSpecificationType or a subtype of it

<AssemblyLot> is a placeholder for any instance of MaterialLotType that are used to compose this material. These MaterialLotType assemblies can have any name, but they shall be referenced using the AssembledFromLot reference and shall be of type MaterialLotType. 

<AssemblySubLot> is a placeholder for any instances of MaterialSublotType that are used to compose this material. These MaterialSublotType assemblies can have any name, but they shall be referenced using the AssembledFromSublot reference and shall be of type MaterialSublotType. 

AssemblyType is flag that indicates if this assembly is a physical or logical assembly. This property is optional on a MaterialSublotType, in that it is only on instances of MaterialSublotType that are being used as an assembly.

AssemblyRelationship is flag that indicates if this assembly is permanent or transient. This property is optional on an instance MaterialLotType, in that it is only on instances of MaterialSublotType that are being used as an assembly.

<Sublot> is a placeholder for any instance of MaterialSublotType that are used to compose this material. These instance of MaterialSublotType can have any name, but they shall be referenced using the MadeUpOfMaterialSublot reference and shall be of type MaterialSublotType or one of its subtypes.

MaterialDefinition is a material definition that is associated to this instance of MaterialLotType.

Status provides optional status information.

StorageLocation is the optional identification of the physical location of the material lot.

Quantity is the amount of material in this lot. 

9 References

9.1 Overview

Figure 2 illustrates the common ReferenceTypes of this standard and their relationship. It includes references that are specific to Equipment, Physical Asset, Personnel or Material Models.

[Figure: Figure 31 - Common ReferenceType]

9.2 Base References

9.2.1 MadeUpOf

The MadeUpOf is an abstract ReferenceType that cannot be used directly. It is a subtype of Aggregates. 

Table 79 - MadeUpOf ReferenceType
Attributes,Value
BrowseName,MadeUpOf
InverseName,ContainedBy
Symmetric,False
IsAbstract,True
References,NodeClass,BrowseName,Comment
Subtype of Aggregates ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe a shared aggregation. The SourceNode contains the TargetNodes. 

The SourceNode of this ReferenceType shall be an Object of ISA95ObjectType or its subtype.

The TargetNode of this ReferenceType shall be an Object of ISA95ObjectType or its subtype.

9.2.2 HasISA95ClassProperty

The HasISA95ClassProperty is a concrete ReferenceType that can be used directly. It is a subtype of HasComponent.

Table 80 - HasISA95ClassProperty ReferenceType
Attributes,Value
BrowseName,HasISA95ClassProperty
InverseName,ISA95ClassPropertyOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasComponent defined in OPC 10000-5

This ReferenceType is used to describe the ownership of an ISA95ClassProperty and is compatible to the "HasPropertyOf" and "may contain nested" relationships described in ISA-95. 

The SourceNode of this ReferenceType shall be a one of subtypes of ISA95ClassType.

The TargetNode of this ReferenceType shall be an ISA95ClassPropertyType or one of its subtypes.

9.2.3 HasISA95Property

The HasISA95Property is a concrete ReferenceType that can be used directly. It is a subtype of the HasComponent.

Table 81 - HasISA95Property ReferenceType
Attributes,Value
BrowseName,HasISA95Property
InverseName,ISA95PropertyOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasComponent ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe the ownership of ISA-95 Property and is compatible to the "HasPropertyOf" relationship described in ISA-95. 

The SourceNode of this ReferenceType shall be one of subtypes of ISA95ObjectType, or one of the subtypes of ISA95PropertyType.

The TargetNode of this ReferenceType shall be an ISA95PropertyType or one of its subtypes.

9.2.4 HasISA95Attribute

The HasISA95Attribute ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of HasComponent ReferenceType.

Table 82 - HasISA95Attribute ReferenceType
Attributes,Value
BrowseName,HasISA95Attribute
InverseName,ISA95AttributeOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasComponent ReferenceType defined in OPC 10000-5

This ReferenceType indicates an ownership of ISA95Attribute.

The SourceNode of this ReferenceType shall be either a Node that is a subtype of ISA95ClassType, a subtype of ISA95ObjectType, a subtype of ISA95ClassPropertyType or a subtype of ISA95PropertyType.

The TargetNode of this ReferenceType shall be an ISA95DataItemType or one of its subtypes.

9.2.5 HasCDTSupplemental

The HasCDTSupplemental is a concrete ReferenceType that can be used directly. It is a subtype of the HasProperty.

Table 83 - HasCDTSupplemental ReferenceType
Attributes,Value
BrowseName,HasCDTSupplemental
InverseName,CDTSupplementalOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasProperty ReferenceType defined in OPC 10000-5

This ReferenceType indicates an ownership of supplemental elements regarding CDT. It allows an ISA-95 aware client to easily detect the supplemental properties associated with dataType that may have been added to a particular instance of a variable. It is a subtype of HasProperty to allow generic client to still access the properties.

The SourceNode of this ReferenceType shall be a subtype of BaseDataType or BaseDataVariableType or one of its subtypes.

The TargetNode of this ReferenceType shall be a PropertyType or one of its subtypes.

9.2.6 LocatedIn

The LocatedIn is a concrete ReferenceType that can be used directly. It is a subtype of the HasProperty.

Table 84 - LocatedIn ReferenceType
Attributes,Value
BrowseName,LocatedIn
InverseName,LocationOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasProperty ReferenceType defined in OPC 10000-5

This ReferenceType indicates physical Location information for an asset.

The SourceNode of this ReferenceType shall be a subtype of BaseDataType or BaseDataVariableType or one of its subtypes.

The TargetNode of this ReferenceType shall be an instance of GeoSpatialLocationType or one of its subtypes.

9.2.7 DefinedBy

The DefinedBy is an abstract ReferenceType that cannot be used directly. It is a subtype of NonHierarchicalReferences. 

Table 85 - DefinedBy ReferenceType
Attributes,Value
BrowseName,DefinedBy
InverseName,DefinitionOf
Symmetric,False
IsAbstract,True
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe a categorization of the SourceNode. The Object identified by the SourceNode has the same features as that defined by the Object specified by TargetNode. 

The SourceNode of this ReferenceType shall be an Object of ISA95ObjectType or its subtype.

The TargetNode of this ReferenceType shall be an Object of ISA95ClassType or its subtype.

9.2.8 TestedBy

The TestedBy ReferenceType is an abstract ReferenceType that cannot be used directly. It is a subtype of NonHierarchicalReferences ReferenceType. 

Table 86 - TestedBy ReferenceType
Attributes,Value
BrowseName,TestedBy
InverseName,TestSpecificationOf
Symmetric,False
IsAbstract,True
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe an ISA-95 Test Specification that is associated with the SourceNode. The Object identified by SourceNode is tested by the ISA-95 Test Specification specified by the TargetNode. 

The SourceNode of this ReferenceType shall be an Object of ISA95PropertyType or its subtypes.

The TargetNode of this ReferenceType shall be an Object of ISA95TestSpecification or its subtype.

9.2.9 ImplementedBy

The ImplementedBy is a concrete ReferenceType that can be used directly. It is a subtype of NonHierarchicalReferences. 

Table 87 - ImplementedBy ReferenceType
Attributes,Value
BrowseName,ImplementedBy
InverseName,ImplementationOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe a relationship between ISA95Equipment and ISA95PhysicalAsset. The SourceNode of this ReferenceType shall be an Object of EquipmentType, PhysicalAssetType or its subtypes.

The TargetNode of this ReferenceType shall be an Object of PhysicalAssetType, EquipmentType or its subtypes.

9.2.10 HasTestResult

The HasTestResult is a concrete ReferenceType that can be used directly. It is a subtype of HasProperty. 

Table 88 - HasTestResult ReferenceType
Attributes,Value
BrowseName,HasTestResult
InverseName,TestResultOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of HasProperty ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe the test results that are associated with an ISA95Property.

The SourceNode of this ReferenceType shall be a Variable or VariableType of ISA95Property or its subtype

The TargetNode of this ReferenceType shall be a Variable of ISA95TestResultType or its subtype.

9.2.11 ResultsForSpecification

The ResultsForSpecification is a concrete ReferenceType that can be used directly. It is a subtype of NonHierarchicalReferences. 

Table 89 - ResultsForSpecification ReferenceType
Attributes,Value
BrowseName,ResultsForSpecification
InverseName,SpecificationForResults
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe the test specification for which these test results apply.

The SourceNode of this ReferenceType shall be a Variable of ISA95TestResultType or a subtype of it.

The TargetNode of this ReferenceType shall be an Object of ISA95TestSpecificationType or a subtype of it.

9.3 Personnel References

9.3.1 DefinedByPersonnelClass

The DefinedByPersonnelClass ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of DefinedBy ReferenceType. 

Table 90 - DefinedByPersonnelClass ReferenceType
Attributes,Value
BrowseName,DefinedByPersonnelClass
InverseName,PersonnelClassOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of DefinedBy defined in 9.2.7.

This ReferenceType is used to describe a categorization of the SourceNode. The Object identified by the SourceNode has the same features as that defined by the Object specified by TargetNode. 

The SourceNode of this ReferenceType shall be an Object of PersonType or its subtype.

The TargetNode of this ReferenceType shall be an Object of PersonnelClassType or its subtype.

9.3.2 TestedByQualificationTest

The TestedBy ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of TestedBy ReferenceType. 

Table 91 - TestedByQualificationTest ReferenceType
Attributes,Value
BrowseName,TestedByQualificationTest
InverseName,QualificationTestOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of TestedBy defined in section 9.2.8.

This ReferenceType is used to describe a qualification test that is associated with the SourceNode. The Object identified by the SourceNode is tested by the qualification test specification specified by the TargetNode. 

The SourceNode of this ReferenceType shall be an Object of PersonnelClassType, PersonType, PersonnelClassPropertyType, PersonPropertyType or its subtypes. 

The TargetNode of this ReferenceType shall be an Object of QualificationTestSpecificationType or its subtype.

9.4 Equipment References

9.4.1 MadeUpOfEquipment

The MadeUpOf is a concrete ReferenceType that can be used directly. It is a subtype of MadeUpOf. 

Table 92 - MadeUpOfEquipment ReferenceType
Attributes,Value
BrowseName,MadeUpOfEquipment
InverseName,ContainedByEquipment
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of MadeUpOf ReferenceType defined in 9.2.1

This ReferenceType is used to describe composition of equipment. The SourceNode contains the TargetNodes. 

The SourceNode of this ReferenceType shall be an Object of EquipmentType or its subtype.

The TargetNode of this ReferenceType shall be an Object of EquipmentType or its subtype.

9.4.2 DefinedByEquipmentClass

The DefinedByEquipmentClass ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of DefinedBy ReferenceType. 

Table 93 - DefinedByEquipmentClass ReferenceType
Attributes,Value
BrowseName,DefinedByEquipmentClass
InverseName,EquipmentClassOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of DefinedBy defined in 9.2.7.

This ReferenceType is used to describe a categorization of the SourceNode. The Object identified by the SourceNode has the same features as that defined by the Object specified by TargetNode. 

The SourceNode of this ReferenceType shall be an Object of EquipmentType or its subtype.

The TargetNode of this ReferenceType shall be an Object of EquipmentClassType or its subtype.

9.4.3 TestedByEquipmentTest

The TestedByEquipmentTest ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of TestedBy ReferenceType. 

Table 94 - TestedByEquipmentTest ReferenceType
Attributes,Value
BrowseName,TestedByEquipmentTest
InverseName,EquipmentTestOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of TestedBy defined in 9.2.8.

This ReferenceType is used to describe a qualification test that is associated with the SourceNode. The Object identified by the SourceNode is tested by the Equipment Capability Test Specification specified by the TargetNode. 

The SourceNode of this ReferenceType shall be an Object of EquipmentType, EquipmentClassType, EquipmentClassPropertyType, EquipmentPropertyType or its subtypes.

The TargetNode of this ReferenceType shall be an Object of EquipmentCapabilityTestSpecificationType or its subtype.

9.5 Physical Asset References

9.5.1 MadeUpOfPhysicalAsset

The MadeUpOfPhysicalAsset is a concrete ReferenceType that can be used directly. It is a subtype of MadeUpOf. 

Table 95 - MadeUpOfPhysicalAsset ReferenceType
Attributes,Value
BrowseName,MadeUpOfPhysicalAsset
InverseName,ContainedByPhysicalAsset
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of madeUpOf ReferenceType defined in 9.2.1

This ReferenceType is used to describe composition of equipment. The SourceNode contains the TargetNodes. 

The SourceNode of this ReferenceType shall be an Object of PhysicalAssetType or its subtype.

The TargetNode of this ReferenceType shall be an Object of PhysicalAssetType or its subtype.

9.5.2 DefinedByPhysicalAssetClass

The DefinedByPhysicalAssetClass ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of DefinedBy ReferenceType. 

Table 96 - DefinedByPhysicalAssetClass ReferenceType
Attributes,Value
BrowseName,DefinedByPhysicalAssetClass
InverseName,PhysicalAssetClassOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of DefinedBy defined in 9.2.7.

This ReferenceType is used to describe a categorization of the SourceNode. The Object identified by the SourceNode has the same features as that defined by the Object specified by TargetNode. 

The SourceNode of this ReferenceType shall be an Object of PhysicalAssetType or its subtype.

The TargetNode of this ReferenceType shall be an Object of PhysicalAssetClassType or its subtype.

9.5.3 TestedByPhysicalAssetTest

The TestedByPhysicalAssetTest ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of TestedBy ReferenceType. 

Table 97 - TestedByPhysicalAssetTest ReferenceType
Attributes,Value
BrowseName,TestedByPhysicalAssetTest
InverseName,PhysicalAssetTestOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of TestedBy defined in section 9.2.8.

This ReferenceType is used to describe a qualification test that is associated with the SourceNode. The Object identified by the SourceNode is tested by the instance of the PhysicalAssetCapabilityTestSpecificationType specified by the TargetNode. 

The SourceNode of this ReferenceType shall be an Object of PhysicalAssetType, PhysicalAssetClassType, PhysicalAssetClassPropertyType, PhysicalAssetPropertyType or its subtypes. 

The TargetNode of this ReferenceType shall be an Object of PhysicalAssetCapabilityTestSpecificationType or its subtype.

9.6 Material References

9.6.1 MadeUpOfMaterialSublot

The MadeUpOfMaterialSublot is a concrete ReferenceType that can be used directly. It is a subtype of MadeUpOf. 

Table 98 - MadeUpOfMaterialSublot ReferenceType
Attributes,Value
BrowseName,MadeUpOfMaterialSublot
InverseName,ContainedByMaterialSublot
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of madeUpOf ReferenceType defined in 9.2.1

This ReferenceType is used to describe composition of equipment. The SourceNode contains the TargetNodes. 

The SourceNode of this ReferenceType shall be an Object of PhysicalAssetType or its subtype.

The TargetNode of this ReferenceType shall be an Object of PhysicalAssetType or its subtype.

9.6.2 DefinedByMaterialClass

The DefinedByMaterialClass is a concrete ReferenceType that can be used directly. It is a subtype of NonHierarchicalReferences. 

Table 99 - DefinedByMaterialClass ReferenceType
Attributes,Value
BrowseName,DefinedByMaterialClass
InverseName,MaterialClassOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of DefinedBy ReferenceType defined in 9.2.7

This ReferenceType is used to describe a categorization of the SourceNode. The Object identified by the SourceNode has the same features as that defined by the Object specified by TargetNode. 

The SourceNode of this ReferenceType shall be an Object of MaterialDefinitionType or its subtype.

The TargetNode of this ReferenceType shall be an Object of MaterialClass or its subtype.

9.6.3 TestedByMaterialTest

The TestedBy ReferenceType is a concrete ReferenceType that can be used directly. It is a subtype of NonHierarchicalReferences ReferenceType. 

Table 100 - TestedByMaterialTest ReferenceType
Attributes,Value
BrowseName,TestedByMaterialTest
InverseName,MaterialTestOf
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe an instance of MaterialTestSpecificationType that is associated with the SourceNode. The Object identified by SourceNode is tested by the instance of a MaterialTestSpecificationType specified by the TargetNode. 

The SourceNode of this ReferenceType shall be an Object of MaterialClassType, MaterialDefinitionType, MaterialLotType, MaterialClassPropertyType, MaterialDefinitionPropertyType, MaterialLotPropertyType or its subtypes.

The TargetNode of this ReferenceType shall be an Object of MaterialTestSpecificationType or its subtype.

9.6.4 AssembledFrom

The AssembledFrom ReferenceType is an abstract ReferenceType. It is a subtype of Aggregate ReferenceType. 

Table 101 - AssembledFrom ReferenceType
Attributes,Value
BrowseName,AssembledFrom
InverseName,Assemblyto
Symmetric,False
IsAbstract,True
References,NodeClass,BrowseName,Comment
Subtype of Aggregates ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe the assemblies that compose a material, where the assemblies are other material.

The SourceNode of this ReferenceType shall be an Object of MaterialDefinitionType, MaterialClassType, MaterialLotType MaterialSublotType, MaterialClassPropertyType, MaterialDefinitionPropertyType, or their subtypes. 

The TargetNode of this ReferenceType shall be shall be an Object of MaterialDefinitionType, MaterialClassType, MaterialLotType MaterialSublotType, MaterialClassPropertyType, MaterialDefinitionPropertyType, or their subtypes.

9.6.5 AssembledFromDefinition

The AssembledFromDefinition ReferenceType is a Concrete ReferenceType hat can be used directly. It is a subtype of AssembledFrom ReferenceType. 

Table 102 - AssembledFromDefinition ReferenceType
Attributes,Value
BrowseName,AssembledFromDefinition
InverseName,AssemblyToDefinition
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of AssembledFrom ReferenceType defined in 9.6.4

This ReferenceType is used to describe the assemblies that compose a material definition where the assemblies are other material classes. 

The SourceNode of this ReferenceType shall be an Object of MaterialDefinitionType, or MaterialDefinitionPropertyType and their subtypes. 

The TargetNode of this ReferenceType shall be MaterialDefinitionType or MaterialDefinitionPropertyType and their subtype.

9.6.6 AssembledFromClass

The AssembledFromClass ReferenceType is a Concrete ReferenceType hat can be used directly. It is a subtype of AssembledFrom ReferenceType. 

Table 103 - AssembledFromClass ReferenceType
Attributes,Value
BrowseName,AssembledFromClass
InverseName,AssemblyToClass
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of AssembledFrom ReferenceType defined in 9.6.4

This ReferenceType is used to describe the assemblies that compose a material class where the assemblies are other material classes. 

The SourceNode of this ReferenceType shall be an Object of MaterialClassType, or MaterialClassPropertyType  and their subtypes. 

The TargetNode of this ReferenceType shall be MaterialClassType or MaterialClassPropertyType and their subtype.

9.6.7 AssembledFromLot

The AssembledFromLot ReferenceType is a Concrete ReferenceType hat can be used directly. It is a subtype of AssembledFrom ReferenceType. 

Table 104 - AssembledFromLot ReferenceType
Attributes,Value
BrowseName,AssembledFromLot
InverseName,AssemblyToLot
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of AssembledFrom ReferenceType defined in 9.6.4

This ReferenceType is used to describe the assemblies that compose a material lot where the assemblies are other material classes. 

The SourceNode of this ReferenceType shall be an Object of MaterialLotType and its subtypes. 

The TargetNode of this ReferenceType shall be MaterialLotType or MaterialSubLotType and their subtype.

9.6.8 AssembledFromSublot

The AssembledFromSublot ReferenceType is a Concrete ReferenceType hat can be used directly. It is a subtype of AssembledFrom ReferenceType. 

Table 105 - AssembledFromLot ReferenceType
Attributes,Value
BrowseName,AssembledFromSublot
InverseName,AssemblyToSublot
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of AssembledFrom ReferenceType defined in 9.6.4

This ReferenceType is used to describe the assemblies that compose a material lot where the assemblies are other material classes. 

The SourceNode of this ReferenceType shall be an Object of MaterialSublotType and its subtypes. 

The TargetNode of this ReferenceType shall be MaterialLotType or MaterialSublotType and their subtype.

10 Profile

10.1 Conformance Unit

10.1.1 Overview

This section defines ConformanceUnits that are specific to the OPC UA ISA-95 Information model. These ConformanceUnits are separated into ConformanceUnits that are Server specific and those that are Client specific.

10.1.2 Server


            Table 107 defines the Server based ConformanceUnits. These units are separated into common items, Physical Asset, Equipment, Personnel and material handling based ConformanceUnits

Table 106 - ISA95 Server Information Model
Category,Title,Description,Derived
Server,ISA95-CCTS Data Representation Model,"Support for ISA95 defined CCTS DataTypes, This includes support for the following types: CDTAmountDecimal CDTBinaryObject CDTCode CDTDateTime CDTGraphic CDTIdentifier CDTMeasure CDTOrdinal CDTPicture CDTRate CDTSound CDTVideo This includes supporting any supplemental properties which are exposed on the DataType. The actual list of supported CDT DataType is provided by this ConformanceUnit. The default values of the any supplemental properties are used or the supplemental property is added to an instance to override its value.",
Server,ISA95-CCTS Data Representation Model Complex,The server automatically adds CCTS Supplemental data properties to any variables that are defined to use the given DataType. The new supplemental properties have a default value that is from the supplemental property on the DataType.,
Server,ISA95-Data Representation Model,"Support for ISA95 define DataTypes, This includes support for the following basic types: CurrencyCode DateString Decimal DecimalString DurationString NormalizedString TimeString The actual list of supported data types is provided by this ConformanceUnit",
Server,ISA95-Base Types,"The Server exposes the ISA95 Basic Type system. This includes: ISA95ClassPropertyType, ISA95PropertyType, ISA95ClassType, ISA95ObjectType and ISA95TestSpecificationType.",
Server,ISA95 - TestResults,The Server supports the ISA95TestResultsDataType and instance of the ISA95TestResultType variable that provide the result in this data type,
Server,ISA95 - ISA95TestResultMeasurementDataType,The Server supports the ISA95TestResultMeasurementDataType and instance of the ISA95TestResultType variable that provide the result in this data type,
Server,ISA95 - Qualification,The server supports test descriptions that are instances of QualificationTestSpecificationType. The server also supports instances of QualificationTestResultType or sub types of it that describe the test results associated with the provided instance of the QualificationTestSpecificationType.,
,,,
Server,ISA95-Personnel Model Types,The Server supports PersonnelClassType and PersonnelClassPropertyType. This includes support for creating subtypes of PersonnelClassType that have predefined instances of PersonnelClassPropertyType.,
Server,ISA95-Person Model Type Instances,The Server supports PersonType and PersonPropertyType. This includes support for instances that are defined against the type. Where these instances will have references to one or more subtypes of PersonnelClassType and will inherit all instances of PersonnelClassPropertyType provided in the referenced PersonnelClassType as instances of PersonPropertyType.,
Server,ISA95-Person Model Subtypes,The Server supports creating sub-types of PersonType where the sub types have predefined PersonnelClassType references and appropriate inheritance of PersonnelClassPropertyType instances. It also includes creating instance against the new sub-types,
Server,ISA95-Person Qualification Test Model,The Server supports Qualification tests for Instance of PersonType and Instances of PersonPropertyType.; this includes support for maintaining test results.,
Server,ISA95-Personnel Qualification Test Model,"The Server supports Qualification tests for PersonnelClassType and for instances of PersonnelClassPropertyType, this include support for maintaining test results.",
,,,
Server,ISA95 - Equipment Capability,The server supports test descriptions that are instances of EquipmentCapabilityTestSpecificationType. The server also supports instances of EquipmentCapabilityTestResultType or sub types of it that describe the test results associated with the provided instance of the EquipmentCapabilityTestSpecificationType.,
Server,ISA95-Equipment Class Model Types,The Server supports EquipmentClassTypes and EquipmentClassPropertyType. This includes support for creating subtypes of EquipmentClassType that have predefined instances of EquipmentClassPropertyType.,
Server,ISA95-Equipment Model Type Instances,"The Server supports EquipmentType and EquipmentPropertyTypes. This includes support for instances that are defined against the type, where these instance will have references to one or more subtypes of EquipmentClassType and will inherit all instances of EquipmentClassPropertyType provided in the referenced EquipmentClassType as instances of EquipmentPropertyType.",
Server,ISA95 - Nested Equipment,The server supports defining EquipmentType that are made up of other EquipmentType,
Server,ISA95 - EquipmentLevel,"The server support defining a hierarchy of equipment instances, where the instances include an EquipmentLevel indication along with a browseable hierarchy structure.",
Server,ISA95 - Equipment Model Subtypes,The Server supports creating sub-types of EquipmentType where the sub types have predefined EquipmentClassType references and appropriate inheritance of EquipmentClassPropertyType instances. It also includes creating instance against the new sub-types,
Server,ISA95-Equipment Capability Test Model,"The Server supports Equipment Capability tests for instance of EquipmentType and Instances of EquipmentPropertyType., this includes support for maintaining test results.",
,,,
Server,ISA95 - AssetAssignment,"Supports instance of ISA95AssetAssignmentType or a sub type of it, to link Physical Assets and Equipment. This includes supporting an associated data type for the VariableType.",
,,,
Server,ISA95 - Physical Asset Capability,The server supports test descriptions that are instances of PhysicalAssetCapabilityTestSpecificationType. The server also supports instances of PhysicalAssetCapabilityTestResultType or sub types of it that describe the test results associated with the provided instance of the PhysicalAssetCapabilityTestSpecificationType.,
Server,ISA95 - PhysicalAsset Class Model Types,The Server supports PhysicalAssetClassTypes and PhysicalAssetClassPropertyType. This includes support for creating subtypes of PhysicalAssetClassType that have predefined instances of PhysicalAssetClassPropertyType.,
Server,ISA95 - PhysicalAsset Manufacture,The Server supports Manufacturer information for PhysicalAssetClassType,
Server,ISA95 -  PhysicalAsset ModelNumber,The Server supports ModelNumber information for PhysicalAssetClassTypes,
Server,ISA95 - PhysicalAsset Model Type Instances,"The Server supports PhysicalAssetType and PhysicalAssetPropertyTypes. This includes support for instances that are defined against the type, where these instance will have references to one or more subtypes of PhysicalAssetClassType and will inherit all instances of PhysicalAssetClassPropertyType provided in the referenced PhysicalAssetClassType as instances of PhysicalAssetPropertyType.",
Server,ISA95 - Nested PhysicalAsset,The server supports defining PhysicalAssetType that are made up of other PhysicalAssetType.,
Server,ISA95 - PhysicalAsset Location,The Server supports GeoSpatialLocationType  and assigning location information to physical assets,
Server,ISA95 -  PhysicalAsset Vendor,The Server supports Vendor information for PhysicalAssetType,
Server,ISA95 - PhysicalAsset Model Subtypes,The Server supports creating sub-types of PhysicalAssetType where the sub types have predefined PhysicalAssetClassType references and appropriate inheritance of PhysicalAssetClassPropertyType instances. It also includes creating instance against the new sub-types,
Server,ISA95-PhysicalAsset Capability Test Model,The Server supports instances of PhysicalAssetCapabilityTestSpecificationType for instances of PhysicalAssetType and Instances of PhysicalAssetPropertyType. This includes support for maintaining test results.,
Server,ISA95 - Material capability,The server supports test descriptions that are instances of MaterialTestSpecificationType. The server also supports instances of MaterialTestResultType or sub types of it that describe the test results associated with the provided instance of the MaterialTestSpecificationType.,
Server,ISA95-Material Class Model Types,The Server supports MaterialClassTypes and MaterialClassPropertyType. This includes support for creating subtypes of MaterialClassType that have predefined instances of MaterialClassPropertyType.,
Server,ISA95-Material Class Model Assembly,The Server supports creating Assemblies of MaterialClassType. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95- Material Class Test,The Server supports instances of MaterialTestSpecificationType for MaterialClassType and Instances of MaterialClassPropertyType.,
Server,ISA95-Material Definition Model Types,The Server supports MaterialDefinitionTypes and MaterialDefinitionPropertyType. This includes support for creating subtypes of MaterialDefinitionType that have predefined instances of MaterialDefinitionPropertyType and predefined References to MaterialClassType Nodes.,
Server,ISA95-Material Definition Model Assembly,The Server supports creating Assemblies of MaterialDefinitionType. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95- Material Definition Test,The Server supports instances of MaterialTestSpecificationType for MaterialDefinitionType and Instances of MaterialDefinitionPropertyType.,
Server,ISA95- MaterialLot Model Type Instances,"The Server supports MaterialLotType and MaterialLotPropertyType. This includes support for instances that are defined against the type, where these instance will have references to a subtype of MaterialDefinitionType and will inherit all instances of MaterialDefinitionPropertyType provided in the referenced MaterialDefinitionType as instances of MaterialLotPropertyType.",
Server,ISA95 - MaterialLot Nested MaterialLot,The server supports defining MaterialLotTypes that are assembled from of other MaterialLotTypes. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95 - MaterialLot Nested MaterialSublot,The server supports defining MaterialLotTypes that are assembled from MaterialSublotTypes. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95 - MaterialLot Madeup MaterialSublot,The server supports defining MaterialLotTypes that are Made up of MaterialSublotTypes.,
Server,ISA95 - MaterialLot Model Subtypes,The Server supports creating sub-types of MaterialLotType where the sub types have predefined MaterialDefinitionType references and appropriate inheritance of MaterialDefinitionPropertyType instances. It also includes creating instance against the new sub-types,
Server,ISA95 -  MaterialLot Status,The Server supports Status information for MaterialLotType,
Server,ISA95 - MaterialLot StorageLocation,The Server supports StorageLocation information for MaterialLotType,
Server,ISA95 - MaterialLot Quantity,The Server supports Quantity information for MaterialLotType,
Server,ISA95- MaterialLot Test,The Server supports instances of MaterialTestSpecificationType for instance of MaterialLotType and instances of MaterialLotPropertyType. This includes support for maintaining test results.,
Server,ISA95- MaterialSublot Model Type Instances,"The Server supports MaterialSublotType and MaterialLotPropertyType. This includes support for instances that are defined against the type, where these instance will have references to a subtype of MaterialDefinitionType and will inherit all instances of MaterialDefinitionPropertyType provided in the referenced MaterialDefinitionType as instances of MaterialLotPropertyType.",
Server,ISA95 - MaterialSublot Nested MaterialLot,The server supports defining MaterialSublotTypes that are assembled from of other MaterialLotTypes. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95 - MaterialSublot Nested MaterialSublot,The server supports defining MaterialSublotTypes that are assembled from MaterialSublotTypes. This includes support for AssemblyType and AssemblyRelationship information,
Server,ISA95 - MaterialSublot Madeup MaterialSublot,The server supports defining MaterialSublotTypes that are Made up of MaterialSublotTypes.,
Server,ISA95 - Materialsublot Model Subtypes,The Server supports creating sub-types of MaterialSublotType where the sub types have predefined MaterialDefinitionType references and appropriate inheritance of MaterialDefinitionPropertyType instances. It also includes creating instance against the new sub-types,
Server,ISA95 -  MaterialSublot Status,The Server supports Status information for MaterialSublotType,
Server,ISA95 - MaterialSublot StorageLocation,The Server supports StorageLocation information for MaterialSublotType,
Server,ISA95 - MaterialSublot Quantity,The Server supports Quantity information for MaterialSublotType,
Server,ISA95- MaterialSublot Test,The Server supports instances of MaterialTestSpecificationType for instance of MaterialSublotType and instances of MaterialLotPropertyType. This includes support for maintaining test results.,

10.1.3 Client


            Table 107 defines the Client based ConformanceUnits. These units are separated into common items, Physical Asset, Equipment, Personnel and material handling based ConformanceUnits

Table 107 - ISA95 Client Information Model
Category,Title,Description,Derived
Client,ISA95-CCTS Data Representation Model Client,The Client supports accessing any supplemental properties which are exposed on the DataType. The default values of the any supplemental properties are used. If the property is overwritten in the instance the instance version of the property is used.,
Client,ISA95-Data Representation Model Client,"The client understands the ISA95 define DataTypes, This includes support for the following basic types: CurrencyCode DateString Decimal DecimalString DurationString NormalizedString TimeString",
,,,
Client,ISA95 - TestResults Client,The Client understands and can make use of the native ISA95TestResultsDataType,
Client,ISA95 - ISA95TestResultMeasurementDataType Client,The Client understands and can make use of the native ISA95TestResultMeasurementDataType,
Client,ISA95 - Qualification Client,The Client understands and can make use of the native test descriptions that are instances of QualificationTestSpecificationType. The Client also understands and can make use of the native QualificationTestResultType or sub types of it that describe the test results associated an instance of the QualificationTestSpecificationType.,
,,,
Client,ISA95-Person Model Type Instances Client,The Client understands and can make use of PersonType and PersonPropertyType. This includes support for instances that are defined against the type.,
Client,ISA95-Person Model Subtypes Client,The Client understands and can make use of sub-types of PersonType. This includes support for instance that are defined against the new sub-types,
Client,ISA95-Person Qualification Test Model Client,The Client understands and can make use of Qualification tests for instances of PersonType and instances of PersonPropertyType. This includes support for maintaining test results.,
Client,ISA95-Personnel Qualification Test Model Client,"The Client understands and can make use of Qualification tests for PersonnelClassType and for instances of PersonnelClassPropertyType, This includes test results.",
,,,
Client,ISA95 - Equipment Capability Client,The Client understands and can make use of test descriptions that are instances of EquipmentCapabilityTestResultType or sub types of it that describe the test results associated with a instance of EquipmentCapabilityTestSpecificationType.,
,,,
Client,ISA95-Equipment Model Type Instances Client,The Client understands and can make use of EquipmentType and EquipmentPropertyTypes. This includes support for instances that are defined against the type.,
Client,ISA95 - Nested Equipment Client,The Client understands and can make use of EquipmentType that are made up of other EquipmentType,
Client,ISA95 - EquipmentLevel Client,"The Client understands and can make use of a hierarchy of Equipment instances, where the instances include an EquipmentLevel indication along with a browseable hierarchy structure.",
Client,ISA95 - Equipment Model Subtypes Client,The Client understands and can make use of sub-types of EquipmentType including instance against the new sub-types,
Client,ISA95-Equipment Capability Test Model Client,The Client understands and can make use of Equipment Capability tests for instance of EquipmentType and Instances of EquipmentPropertyType. This includes support for test results.,
,,,
Client,ISA95 - Physical Asset Capability Client,The Client understands and can make use of test descriptions that are instances of PhysicalAssetCapabilityTestSpecificationType. The Client also understands and can make use of instances of PhysicalAssetCapabilityTestResultType or sub types of it that describe the test results.,
,,,
Client,ISA95 - PhysicalAsset Manufacture Client,The Client understands and can make use of Manufacturer information for PhysicalAsset ClassTypes,
Client,ISA95 -  PhysicalAsset ModelNumber Client,The Client understands and can make use of ModelNumber information for PhysicalAssetClassTypes,
Client,ISA95 - PhysicalAsset Model Type Instances Client,"The Client understands and can make use of PhysicalAssetType and PhysicalAssetPropertyTypes. This includes instances that are defined against the type,.",
Client,ISA95 - Nested PhysicalAsset Client,The Client understands and can make use of PhysicalAssetTypes that are made up of other PhysicalAssetTypes.,
Client,ISA95 - PhysicalAsset Location Client,The Client understands and can make use of GeoSpatialLocationType  and location information on physical assets,
Client,ISA95 -  PhysicalAsset Vendor Client,The Client understands and can make use of Vendor information for PhysicalAsset Types,
Client,ISA95 - PhysicalAsset Model Subtypes Client,The Client understands and can make use of sub-types of PhysicalAssetType including instance of the  sub-types,
Client,ISA95-PhysicalAsset Capability Test Model Client,The Client understands and can make use of instances of PhysicalAssetCapabilityTestSpecificationType including test results.,
,,,
Client,ISA95 - Material capability Client,The Client understands and can make use of test descriptions that are instances of MaterialTestSpecificationType. The Client also understands and can make use of instances of MaterialTestResultType or sub types of it.,
Client,ISA95-Material Class Model Assembly Client,The Client understands and can make use of Assemblies of MaterialClassType. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95- Material Class Test Client,The Client understands and can make use of instances of MaterialTestSpecificationType for MaterialClassType and Instances of MaterialClassPropertyType.,
Client,ISA95-Material Definition Model Types Client,The Client understands and can make use of MaterialDefinitionTypes and MaterialDefinitionPropertyType.,
Client,ISA95-Material Definition Model Assembly Client,The Client understands and can make use of Assemblies of MaterialDefinitionType. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95- Material Definition Test Client,The Client understands and can make use of instances of MaterialTestSpecificationType for MaterialDefinitionType and Instances of MaterialDefinitionPropertyType.,
Client,ISA95- MaterialLot Model Type Instances Client,The Client understands and can make use of MaterialLotType and MaterialLotPropertyType. This includes instances that are defined against the type.,
Client,ISA95 - MaterialLot Nested MaterialLot Client,The Client understands and can make use of MaterialLotTypes that are assembled from of other MaterialLotTypes. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95 - MaterialLot Nested MaterialSublot Client,The Client understands and can make use of MaterialLotTypes that are assembled from MaterialSublotTypes. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95 - MaterialLot Madeup MaterialSublot Client,The Client understands and can make use of MaterialLotTypes that are MadeUpOf  MaterialSublotTypes.,
Client,ISA95 - MaterialLot Model Subtypes Client,The Client understands and can make use of sub-types of MaterialLotType where the sub types.,
Client,ISA95 -  MaterialLot Status Client,The Client understands and can make use of Status information for MaterialLotType,
Client,ISA95 - MaterialLot StorageLocation Client,The Client understands and can make use of StorageLocation information for MaterialLotType,
Client,ISA95 - MaterialLot Quantity Client,The Client understands and can make use of Quantity information for MaterialLotType,
Client,ISA95- MaterialLot Test Client,The Client understands and can make use of instances of MaterialTestSpecificationType for instance of MaterialLotType and instances of MaterialLotPropertyType. This includes maintaining test results.,
Client,ISA95- MaterialSublot Model Type Instances Client,The Client understands and can make use of MaterialSublotType and MaterialLotPropertyType. This includes instances that are defined against the type.,
Client,ISA95 - MaterialSublot Nested MaterialLot Client,The Client understands and can make use of MaterialSublotTypes that are assembled from of other MaterialLotTypes. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95 - MaterialSublot Nested MaterialSublot Client,The Client understands and can make use of MaterialSublotTypes that are assembled from MaterialSublotTypes. This includes AssemblyType and AssemblyRelationship information,
Client,ISA95 - MaterialSublot Madeup MaterialSublot Client,The Client understands and can make use of MaterialSublotTypes that are Made up of MaterialSublotTypes.,
Client,ISA95 - Materialsublot Model Subtypes Client,The Client understands and can make use of creating sub-types of MaterialSublotType. The Client understands and can make use of instance for the sub-types,
Client,ISA95 -  MaterialSublot Status Client,The Client understands and can make use of Status information for MaterialSublotType,
Client,ISA95 - MaterialSublot StorageLocation Client,The Client understands and can make use of StorageLocation information for MaterialSublotType,
Client,ISA95 - MaterialSublot Quantity Client,The Client understands and can make use of Quantity information for MaterialSublotType,
Client,ISA95- MaterialSublot Test Client,The Client understands and can make use of instances of MaterialTestSpecificationType for instance of MaterialSublotType and instances of MaterialLotPropertyType. This includes test results.,

10.2 Facet

10.2.1 Overview

The section describes the various Facets that are provided as part of the OPC UA ISA-95 information model. These Facets include information model ConformanceUnits, but they also include ConformanceUnits or Facets from the base OPC UA Profile specification.

Table 108 - ISA95 Profiles
Profile,Related Category,URI
ISA95 Base Server Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/BaseServer
ISA95 Base Personnel Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/PersonnelServer
ISA95 Extended Personnel Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/ExtendedPersonnelServer
ISA95 Base Equipment Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/EquipmentServer
ISA95 Extended Equipment Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/ExtendedEquipmentServer
ISA95 Base Physical Asset Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/PhysicalAssetServer
ISA95 Extended Physical Asset Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/ExtendedPhysicalAssetServer
ISA95 Physical Asset Related Equipment Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/PhysicalAssetRelatedEquipmentServer
ISA95 Base MaterialClass Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/MaterialClassServer
ISA95 Base MaterialLot Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/MaterialLotServer
ISA95 Extended MaterialLot Model Server  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Server/ISA95/ExtendedMaterialServer
ISA95 Base Client Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/BaseClient
ISA95 Base Personnel Model Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/PersonnelClient
ISA95 Extended Personnel Model Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/ExtendedPersonnelClient
ISA95 Base Equipment Model Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/EquipmentClient
ISA95 Extended Equipment Model Client Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/ExtendedEquipmentClient
ISA95 Base Physical Asset Model Client Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/PhysicalAssetClient
ISA95 Extended Physical Asset Model Client Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/ExtendedPhysicalAssetClient
ISA95 Physical Asset Related Equipment Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/PhysicalAssetRelatedEquipmentClient
ISA95 Base MaterialClass Model Client Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/MaterialClassClient
ISA95 Base MaterialLot Model Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/MaterialLotClient
ISA95 Extended MaterialLot Model Client  Facet,ISA95 Model,http://opcfoundation.org/UA-Profile/Client/ISA95/ExtendedMaterialLotClient

10.2.2 Server

10.2.2.1 ISA95 Base Server Facet

The profile describes the base characteristics that all OPC UA Server that are exposing the ISA-95 Information model. Additional profile will define support for various information models that are part of the overall ISA-95 information model.

Table 109 - ISA95 Base Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95-CCTS Data Representation Model,False
ISA95 Model,ISA95-CCTS Data Representation Model Complex,True
ISA95 Model,ISA95-Data Representation Model,False
ISA95 Model,ISA95-Base Types,False
ISA95 Model,ISA95 - TestResults,True
ISA95 Model,ISA95 - ISA95TestResultMeasurementDataType,True
ISA95 Model,ISA95 - Qualification,False

10.2.2.2 ISA95 Base Personnel Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Personnel Information model. 

Table 110 - ISA95 Base Personnel Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95-Personnel Model Types,False
ISA95 Model,ISA95-Person Model Type Instances,False
ISA95 Model,ISA95-Person Qualification Test Model,False
ISA95 Model,ISA95-Personnel Qualification Test Model,False
Profile,ISA95 Base Server Facet,False

10.2.2.3 ISA95 Extended Personnel Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Personnel Information model including the addition of defining subtype of PersonType. 

Table 111 - ISA95 Extended Personnel Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Server Facet,False
ISA95 Model,ISA95 - Person Model Subtypes,False
,,

10.2.2.4 ISA95 Base Equipment Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Equipment Information model. 

Table 112 - ISA95 Base Equipment Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Equipment capability,False
ISA95 Model,ISA95-Equipment Class Model Types,False
ISA95 Model,ISA95-Equipment Model Type Instances,False
ISA95 Model,ISA95 - Nested Equipment,True
ISA95 Model,ISA95 - EquipmentLevel,True
ISA95 Model,ISA95-Equipment Qualification Test Model,False
Profile,ISA95 Base Server Facet,False

10.2.2.5 ISA95 Extended Equipment Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Equipment Information model including the addition of defining subtypes of EquipmentType. 

Table 113 - ISA95 Extended Equipment Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Equipment Model Server Facet,False
ISA95 Model,ISA95 - Equipment Model Subtypes,False

10.2.2.6 ISA95 Base Physical Asset Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Physical Asset Information model. 

Table 114 - ISA95 Base Physical Asset Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Physical Asset capability,False
ISA95 Model,ISA95-PhysicalAsset Class Model Types,False
ISA95 Model,ISA95 - PhysicalAsset Manufacture,True
ISA95 Model,ISA95 -  PhysicalAsset ModelNumber,True
ISA95 Model,ISA95 - PhysicalAsset Model Type Instances,False
ISA95 Model,ISA95 - Nested PhysicalAsset,True
ISA95 Model,ISA95 - PhysicalAsset Location,True
ISA95 Model,ISA95 - PhysicalAsset Vendor,True
ISA95 Model,ISA95-PhysicalAsset Qualification Test Model,False
Profile,ISA95 Base Server Facet,False

10.2.2.7 ISA95 Extended Physical Asset Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Physical Asset Information model including the addition of defining subtypes of PhysicalAssetType. 

Table 115 - ISA95 Extended Physical Asset Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Physical Asset Model Server Facet,False
ISA95 Model,ISA95 - PhysicalAsset Model Subtypes,False

10.2.2.8 ISA95 Physical Asset Related Equipment Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Physical Asset Information model including the addition of defining subtypes of Physical Asset Type. 

Table 116 - ISA95 Physical Asset Related Equipment Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Physical Asset Model Server Facet,False
Profile,ISA95 Base Equipment Model Server Facet,False
ISA95 Model,ISA95 - AssetAssignment,False

10.2.2.9 ISA95 Base MaterialClass Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Material Class Information model. 

Table 117 - ISA95 Base MaterialClass Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Material capability,False
ISA95 Model,ISA95-Material Class Model Types,False
ISA95 Model,ISA95-Material Class Model Assembly,True
ISA95 Model,ISA95- Material Class Test,True
ISA95 Model,ISA95-Material Definition Model Types,False
ISA95 Model,ISA95-Material Definition Model Assembly,True
ISA95 Model,ISA95- Material Definition Test,True
Profile,ISA95 Base Server Facet,False

10.2.2.10 ISA95 Base MaterialLot Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Material Lot Information model. 

Table 118 - ISA95 Base MaterialLot Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95- MaterialLot Model Type Instances,False
ISA95 Model,ISA95 - MaterialLot Nested MaterialLot,True
ISA95 Model,ISA95 - MaterialLot Madeup MaterialSublot,True
ISA95 Model,ISA95 -  MaterialLot Status,True
ISA95 Model,ISA95 - MaterialLotStorageLocation,True
ISA95 Model,ISA95 - MaterialLot Quantity,True
ISA95 Model,ISA95- MaterialLot Test,True
ISA95 Model,ISA95- MaterialSublot Model Type Instances,False
ISA95 Model,ISA95 - MaterialSublot Nested MaterialLot,True
ISA95 Model,ISA95 - MaterialSublot Nested MaterialSublot,True
ISA95 Model,ISA95 - MaterialSublot Madeup MaterialSublot,True
ISA95 Model,ISA95 -  MaterialSublot Status,True
ISA95 Model,ISA95 - MaterialSublot StorageLocation,True
ISA95 Model,ISA95 - MaterialSublot Quantity,True
ISA95 Model,ISA95- MaterialSublot Test,True
Profile,ISA95 Base Server Facet,False

10.2.2.11 ISA95 Extended MaterialLot Model Server Facet

The profile describes the base characteristics for an OPC UA Server that is exposing the ISA-95 Material Lot Information model including the addition of defining subtype of MaterialLotType and MaterialSublotType. 

Table 119 - ISA95 Extended MaterialLot Model Server Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Material Model Server Facet,False
ISA95 Model,ISA95 - MaterialLot Model Subtypes,False
ISA95 Model,ISA95 - MaterialSublot Model Subtypes,False

10.2.3 Client

10.2.3.1 ISA95 Base Client Facet

The profile describes the base characteristics for all OPC UA Clients that make use of the ISA-95 Information model. Additional profiles will define support for various information models that are part of the overall ISA-95 information model.

Table 120 - ISA95 Base Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95-CCTS Data Representation Model Client,False
ISA95 Model,ISA95-Data Representation Model Client,False
ISA95 Model,ISA95 - TestResults Client,True
ISA95 Model,ISA95 - ISA95TestResultMeasurementDataType Client,True
ISA95 Model,ISA95 - Qualification Client,False

10.2.3.2 ISA95 Base Personnel Model Client Facet

The profile describes the base characteristics for an OPC UA Client using the ISA-95 Personnel Information model. 

Table 121 - ISA95 Base Personnel Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95-Person Model Type Instances Client,False
ISA95 Model,ISA95-Person Qualification Test Model Client,False
ISA95 Model,ISA95-Personnel Qualification Test Model Client,False
Profile,ISA95 Base Client Facet,False

10.2.3.3 ISA95 Extended Personnel Model Client Facet

The profile describes the base characteristics for an OPC UA Client using the ISA-95 Personnel Information model including subtypes of PersonType. 

Table 122 - ISA95 Extended Personnel Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Client Facet,False
ISA95 Model,ISA95 - Person Model Subtypes Client,False

10.2.3.4 ISA95 Base Equipment Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Equipment Information model. 

Table 123 - ISA95 Base Equipment Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Equipment Capability Client,False
ISA95 Model,ISA95-Equipment Model Type Instances Client,False
ISA95 Model,ISA95 - Nested Equipment Client,True
ISA95 Model,ISA95 - EquipmentLevel Client,True
ISA95 Model,ISA95-Equipment Qualification Test Model Client,False
Profile,ISA95 Base Client Facet,False

10.2.3.5 ISA95 Extended Equipment Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Equipment Information model including subtypes of EquipmentType. 

Table 124 - ISA95 Extended Equipment Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Equipment Model Client Facet,False
ISA95 Model,ISA95 - Equipment Model Subtypes Client,False

10.2.3.6 ISA95 Base Physical Asset Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Physical Asset Information model. 

Table 125 - ISA95 Base Physical Asset Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Physical Asset Capability Client,False
ISA95 Model,ISA95 - PhysicalAsset Manufacture Client,True
ISA95 Model,ISA95 -  PhysicalAsset ModelNumber Client,True
ISA95 Model,ISA95 - PhysicalAsset Model Type Instances Client,False
ISA95 Model,ISA95 - Nested PhysicalAsset Client,True
ISA95 Model,ISA95 - PhysicalAsset Location Client,True
ISA95 Model,ISA95 - PhysicalAsset Vendor Client,True
ISA95 Model,ISA95-PhysicalAsset Qualification Test Model Client,False
Profile,ISA95 Base Client Facet,False

10.2.3.7 ISA95 Extended Physical Asset Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Personnel Information model including subtypes of PersonType. 

Table 126 - ISA95 Extended Physical Asset Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Physical Asset Model Client Facet,False
ISA95 Model,ISA95 - PhysicalAsset Model Subtypes Client,False

10.2.3.8 ISA95 Base MaterialClass Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Material Information model. 

Table 127 - ISA95 Base MaterialClass Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95 - Material capability Client,False
ISA95 Model,ISA95-Material Class Model Types Client,False
ISA95 Model,ISA95-Material Class Model Assembly Client,True
ISA95 Model,ISA95- Material Class Test Client,True
ISA95 Model,ISA95-Material Definition Model Types Client,False
ISA95 Model,ISA95-Material Definition Model Assembly Client,True
ISA95 Model,ISA95- Material Definition Test Client,True
Profile,ISA95 Base Client Facet,False

10.2.3.9 ISA95 Base MaterialLot Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Material Information model. 

Table 128 - ISA95 Base MaterialLot Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
ISA95 Model,ISA95- MaterialLot Model Type Instances Client,False
ISA95 Model,ISA95 - MaterialLot Nested MaterialLot Client,True
ISA95 Model,ISA95 - MaterialLot Madeup MaterialSublot Client,True
ISA95 Model,ISA95 -  MaterialLot Status Client,True
ISA95 Model,ISA95 - MaterialLotStorageLocation Client,True
ISA95 Model,ISA95 - MaterialLot Quantity Client,True
ISA95 Model,ISA95- MaterialLot Test Client,True
ISA95 Model,ISA95- MaterialSublot Model Type Instances Client,False
ISA95 Model,ISA95 - MaterialSublot Nested MaterialLot Client,True
ISA95 Model,ISA95 - MaterialSublot Nested MaterialSublot Client,True
ISA95 Model,ISA95 - MaterialSublot Madeup MaterialSublot Client,True
ISA95 Model,ISA95 -  MaterialSublot Status Client,True
ISA95 Model,ISA95 - MaterialSublot StorageLocation Client,True
ISA95 Model,ISA95 - MaterialSublot Quantity Client,True
ISA95 Model,ISA95- MaterialSublot Test Client,True
Profile,ISA95 Base Client Facet,False

10.2.3.10 ISA95 Extended MaterialLot Model Client Facet

The profile describes the base characteristics for an OPC UA Client that is using the ISA-95 Material Information model including subtypes of MaterialLotType and MaterialSublotType. 

Table 129 - ISA95 Extended MaterialLot Model Client Facet
Group,Conformance Unit /                                                 Profile                                               Title,Optional
Profile,ISA95 Base Material Model Client Facet,False
ISA95 Model,ISA95 - MaterialLot Model Subtypes Client,False
ISA95 Model,ISA95 - MaterialSublot Model Subtypes Client,False

Annex A XML Representation of Model

The following section is a listing of the XML NodeSet file that is a definition of the information model generated by this standard. This NodeSet description is also available from the OPC Foundation web site (http://www.opcfoundation.org/UA/schemas/ISA-95/1.00/) as an XML file. It uses the import/export format defined in OPC UA OPC 10000-6

Annex B Untitled

Annex C ISA-95 Mapping (Normative)

CDT

CDT,OPC UA
Data Type,Primitive Type,Data Type,Base Data Type
Amount,Decimal,CDTAmountDecimal,ByteString
Binary Object,Binary,CDTBinaryObject,ByteString
Graphic,Binary,CDTGraphic,ByteString
Picture,Binary,CDTPicture,ByteString
Sound,Binary,CDTSound,ByteString
Video,Binary,CDTVideo,ByteString
Code,String,CDTCode,Enumeration
DateTime,TimePoint,CDTDateTime,DateTime
Identifier,String,CDTIdentifier,String
Indicator,Boolean,CDTIndicator,Boolean
Measure,Decimal,CDTMeasureDecimal,ByteString
,Double,CDTMeasureDouble,Double
,Float,CDTMeasureFloat,Float
,Integer,CDTMeasureInt64,Int64
,,CDTMeasureInt32,Int32
Name,String,CDTName,String
Numeric,Decimal,CDTNumberDecimal,ByteString
,Double,CDTNumberDouble,Double
,Float,CDTNumberFloat,Float
,Integer,CDTNumberInt64,Int64
,,CDTNumberInt32,Int32
Ordinal,Integer,CDTOrdinal,Int32
Percent,Decimal,N/A,N/A
,Double,CDTPercentDouble,Double
,Float,CDTPercentFloat,Float
,Integer,N/A,N/A
Ratio,Decimal,CDTRatioDecimal,ByteString
,Double,CDTRatioDouble,Double
,Float,CDTRatioFloat,Float
,Integer,CDTRatioInt64,Int64
,,CDTRatioInt32,Int32
Value,Decimal,CDTValueDecimal,ByteString
,Double,CDTValueDouble,Double
,Float,CDTValueFloat,Float
,Integer,CDTValueInt64,Int64
,,CDTValueInt32,Int32
,String,CDTValueString,String
Quantity,Decimal,CDTQuantityDecimal,ByteString
,Double,CDTQuantityDouble,Double
,Float,CDTQuantityFloat,Float
,Integer,CDTQuantityInt64,Int64
,,CDTQuantityInt32,Int32
Rate,Decimal,CDTRateDecimal,ByteString
,Double,CDTRateDouble,Double
,Float,CDTRateFloat,Float
Text,String,CDTText,String
Date,TimePoint,CDTDate,Date
Time,TimePoint,CDTTime,DateTime

C.1 Generic models

ISA-95,OPC UA
Model,Type,Model,Type
Has property of,ISA95Association,HasISA95ClassProperty,Reference
Has value for,ISA95Association,HasISA95Property,Reference
May contain nested,ISA95Association,HasISA95(Class)Property,Reference
N/A,ISA95Association,HasISA95Attribute,Reference
Records the execution of,ISA95Association,N/A,Reference
May be made up of,ISA95Association,MadeUpOf,Reference
Defined by,ISA95Association,DefinedBy,Reference
Is tested by an,ISA95Association,TestedBy,Reference
Implemented By,ISA95Association,EquipmentOf,Reference
N/A,N/A,AssociateTo,Reference
N/A,N/A,ISA95EquipmentLevelEnum,DataType
N/A,N/A,ISA95TestResultDataType,DataType
N/A,N/A,ISA95AssetAssignmentDataType,DataType
Hierarchy scope,ISA95Attribute,ISA95HierarchyScopeType,DataVariable
N/A,N/A,ISA95TestResultType,DataVariable
N/A,N/A,ISA95AssetAssignmentType,DataVariable
N/A,N/A,ISA95ClassType,Object
N/A,N/A,ISA95ObjectType,Object
N/A,N/A,ISA95TestSpecificationType,Object

Personnel Information

ISA-95,OPC UA
Model,Type,Model,Type
QualificationTestResult,ISA95Object,QualificationTestResultType,DataVariable
Personnel Class Property,ISA95Property,PersonnelClassPropertyType,DataVariable
Person Property,ISA95Property,PersonPropertyType,DataVariable
Personnel,ISA95Object,PersonnelClassType,Object
Person,ISA95Object,PersonType,Object
QualificationTestSpecification,ISA95Object,QualificationTestSpecificationType,Object
Defined by,ISA95Association,DefinedByPersonnelClass,Reference
Is tested by an,ISA95Association,ConformsToQualificationTest,Reference

Role Based Equipment Information

ISA-95,OPC UA
Model,Type,Model,Type
EquipmentCapabilityTestResult,ISA95Object,EquipmentCapabilityTestResultType,DataVariable
EquipmentClass Property,ISA95Property,EquipmentClassPropertyType,DataVariable
EquipmentProperty,ISA95Property,EquipmentPropertyType,DataVariable
EquipmentClass,ISA95Object,EquipmentClassType,Object
Equipment,ISA95Object,EquipmentType,Object
EquipmentCapabilityTestSpecification,ISA95Object,EquipmentCapabilityTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Physical Asset Information 

ISA-95,OPC UA
Model,Type,Model,Type
PhysicalAssetCapabilityTestResult,ISA95Object,PhysicalAssetCapabilityTestResultType,DataVariable
PhysicalAssetClass Property,ISA95Property,PhysicalAssetClassPropertyType,DataVariable
PhysicalAssetProperty,ISA95Property,PhysicalAssetPropertyType,DataVariable
PhysicalAssetClass,ISA95Object,PhysicalAssetClassType,Object
PhysicalAsset,ISA95Object,PhysicalAssetType,Object
PhysicalAssetCapabilityTestSpecification,ISA95Object,PhysicalAssetCapabilityTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Material Handling Information

ISA-95,OPC UA
Model,Type,Model,Type
QATestResult,ISA95Object,MaterialTestResultType,DataVariable
MaterialClass Property,ISA95Property,MaterialClassPropertyType,DataVariable
MaterialLotProperty,ISA95Property,MaterialLotPropertyType,DataVariable
MaterialDefinitionProperty,ISA95Property,MaterialDefinitionPropertyType,DataVariable
MaterialClass,ISA95Object,MaterialClassType,Object
MaterialDefinition,ISA95Object,MaterialDefinitionType,Object
MaterialLot,ISA95Object,MaterialLotTYpe,Object
MaterialSublot,ISA95Object,MaterialSubLotType,Object
MaterialTestSpecification,ISA95Object,MaterialTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Annex D B2MML Mapping (Informative)

Overview

This annex provides a mapping of the OPC UA ISA-95 information model to B2MML; conversely it also provides a mapping from B2MML to the OPC UA ISA-95 information model. This section is informative only in that B2MML is not a standard and as such multiple variation of it may exist. This mapping is for a common version, but may not apply to all implementation of B2MML.

Common

B2MML Core Component Type,OPC UA
Type Name,Type,Model,Type
AmountType,Data type,CDTAmountDecimal,DataType
BinaryObjectType,Data type,CDTBinaryObject,DataType
CodeType,Data type,CDTCode,DataType
DateTimeType,Data type,CDTDateTime,DataType
IdentifierType,Data type,CDTIdentifier,DataType
IndicatorType,Data type,CDTIndicator,DataType
MeasureType,Data type,CDTMeasureDecimal,DataType
,,CDTMeasureDouble,DataType
,,CDTMeasureFloat,DataType
,,CDTMeasureInt64,DataType
,,CDTMeasureInt32,DataType
NameType,Data type,CDTName,DataType
NumericType,Data type,CDTNumberDecimal,DataType
,,CDTNumberDouble,DataType
,,CDTNumberFloat,DataType
,,CDTNumberInt64,DataType
,,CDTNumberInt32,DataType
,,CDTOrdinal,DataType
,,CDTPercentDouble,DataType
,,CDTPercentFloat,DataType
,,CDTRateDouble,DataType
,,CDTRateFloat,DataType
,,CDTRatioDouble,DataType
,,CDTRatioFloat,DataType
,,CDTRatioInt64,DataType
,,CDTRatioInt32,DataType
,,CDTValueDecimal,DataType
,,CDTValueDouble,DataType
,,CDTValueFloat,DataType
,,CDTValueInt64,DataType
,,CDTValueInt32,DataType
QuantityType,Data type,CDTQuantityDecimal,DataType
,,CDTQuantityDouble,DataType
,,CDTQuantityFloat,DataType
,,CDTQuantityInt64,DataType
,,CDTQuantityInt32,DataType
TextType,Data type,CDTText,DataType
,,CDTValueString,DataType
,,CDTDate,DataType
,,CDTTime,DataType

Note: The conversion of measurement data from decimal to float or double can result in a loss of precision.

Personnel Information

B2MML,OPC UA
Model,Type,Model,Type
QualificationTestResult,ISA95Object,QualificationTestResultType,DataVariable
Personnel Class Property,ISA95Property,PersonnelClassPropertyType,DataVariable
Person Property,ISA95Property,PersonPropertyType,DataVariable
Personnel,ISA95Object,PersonnelClassType,Object
Person,ISA95Object,PersonType,Object
QualificationTestSpecification,ISA95Object,QualificationTestSpecificationType,Object
Defined by,ISA95Association,DefinedByPersonnelClass,Reference
Is tested by an,ISA95Association,ConformsToQualificationTest,Reference

Role Based Equipment Information

B2MML,OPC UA
Model,Type,Model,Type
EquipmentCapabilityTestResult,ISA95Object,EquipmentCapabilityTestResultType,DataVariable
EquipmentClass Property,ISA95Property,EquipmentClassPropertyType,DataVariable
EquipmentProperty,ISA95Property,EquipmentPropertyType,DataVariable
EquipmentClass,ISA95Object,EquipmentClassType,Object
Equipment,ISA95Object,EquipmentType,Object
EquipmentCapabilityTestSpecification,ISA95Object,EquipmentCapabilityTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Physical Asset Information 

B2MML,OPC UA
Model,Type,Model,Type
PhysicalAssetCapabilityTestResult,ISA95Object,PhysicalAssetCapabilityTestResultType,DataVariable
PhysicalAssetClass Property,ISA95Property,PhysicalAssetClassPropertyType,DataVariable
PhysicalAssetProperty,ISA95Property,PhysicalAssetPropertyType,DataVariable
PhysicalAssetClass,ISA95Object,PhysicalAssetClassType,Object
PhysicalAsset,ISA95Object,PhysicalAssetType,Object
PhysicalAssetCapabilityTestSpecification,ISA95Object,PhysicalAssetCapabilityTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Material Handling Information

B2MML,OPC UA
Model,Type,Model,Type
QATestResult,ISA95Object,MaterialTestResultType,DataVariable
MaterialClass Property,ISA95Property,MaterialClassPropertyType,DataVariable
MaterialLotProperty,ISA95Property,MaterialLotPropertyType,DataVariable
MaterialDefinitionProperty,ISA95Property,MaterialDefinitionPropertyType,DataVariable
MaterialClass,ISA95Object,MaterialClassType,Object
MaterialDefinition,ISA95Object,MaterialDefinitionType,Object
MaterialLot,ISA95Object,MaterialLotTYpe,Object
MaterialSublot,ISA95Object,MaterialSubLotType,Object
MaterialTestSpecification,ISA95Object,MaterialTestSpecificationType,Object
Defines Procedure for Obtaining an,ISA95Association,,
Maps to,ISA95Association,,

Annex E xtensions

ISA95HierarchyScopeType

The ISA95HierarchyScopeType is a concrete VariableType that can be used directly. It is a subtype of BaseDataVariableType 

This VariableType indicates where the exchanged information fits within the role base equipment hierarchy defined in ISA-95. It defines the scope of the exchanged information, such as a site or area for which the information is relevant.

Table 130 - ISA95HierarchyScopeType definition
Attribute,Value
BrowseName,ISA95HierarchyScopeType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,ISA95EquipmentElementLevelEnum
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in OPC 10000-5
HasComponent,Variable,OtherValue,String,TextItemType,Optional
HasComponent,Variable,<SubScope>,ISA95Equipment ElementLevelEnum,ISA95HierarchyScopeType,Optional
ToEquipmentScope,Object,<Equipment>,,ISA95EquipmentType,Optional
HasProperty,Variable,EnumStrings,String,,Mandatory


        OtherValue defines a customized hierarchy scope. If Value attribute is set to "OTHER_14", then OtherValue shall be identification of the hierarchy scope.


        SubScope indicates a sub hierarchy definition.


        <Equipment> defines an ISA95EquipmentType Object that this variable is associated with. 

ToEquipmentScope

The ToEquipmentScope is a concrete ReferenceType that can be used directly. It is a subtype of NonHierarchicalReferences. 

Table 131 - ToEquipmentScope ReferenceType
Attributes,Value
BrowseName,ToEquipmentScope
InverseName,ToHierarchyScope
Symmetric,False
IsAbstract,False
References,NodeClass,BrowseName,Comment
Subtype of NonHierarchicalReferences ReferenceType defined in OPC 10000-5

This ReferenceType is used to describe the Equipment that an ISA95HierarchyScope variable is to be associated with.

The SourceNode of this ReferenceType shall be a Variable or VariableType of ISA95HierarchyScopeType or its subtype

The TargetNode of this ReferenceType shall be an Object of ISA95EquipmentType or its subtype.

Company

The following definition illustrates what a company definition may look like. This definition will be used in examples of the ISA-95 information model, but another implementation may choose to represent the information a different manner. In some systems it maybe simply is a reference to some other system that contains the actual company information.

The company information includes address information of the company. This information is available both as a dataType (see Table 132 and Table 133) and as a VariableType (see Table 134).. This combination allows the information to access as a block or individually.

Table 132 - AddressDataType Structure
Name,Type,Description
AddressDataType,Structure,Information that describes an address.
Street,LocalizedText,The street
City,LocalizedText,The city
State,LocalizedText,The state or region
Country,LocalizedText,The country
PostalCode,LocalizedText,The postal code

Its representation in the AddressSpace is defined in a below table.

Table 133 - AddressDataType Definition
Attributes,Value
BrowseName,AddressDataType

Table 134 - AddressVariableType definition
Attribute,Value
BrowseName,AddressVariableType
IsAbstract,False
ValueRank,0
DataType,AddressDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the CompanyType defined in  XXXX
HasProperty,Variable,Street,LocalizedText,BaseDataVariableType,Mandatory
HasProperty,Variable,City,LocalizedText,BaseDataVariableType,Mandatory
HasProperty,Variable,State,LocalizedText,BaseDataVariableType,Mandatory
HasProperty,Variable,Country,LocalizedText,BaseDataVariableType,Mandatory
HasProperty,Variable,PostalCode,LocalizedText,BaseDataVariableType,Mandatory
HasProperty,Variable,Street,LocalizedText,BaseDataVariableType,Mandatory
,,,,,

The company include contact information for key personnel at the company. This information is available both as a DataType and as a variable type. This combination allows the information to access as a block of individually.

Table 135 - ContactDataType Structure
Name,Type,Description
ContactDataType,Structure,Information that describes an address.
Title,LocalizedText,"Mr, Mrs, Ms, Dr, Sir,…."
GivenName,LocalizedText,
FamilyName,LocalizedText,
PhoneNumber,String,
Email,LocalizedText,
AltPhoneNumber,String,Alternate Phone Number
AltEmail,LocalizedText,Alternate email address

Its representation in the AddressSpace is defined in a below table.

Table 136 - ContactDataType Definition
Attributes,Value
BrowseName,ContactDataType

Table 137 - ContactVariableType Type definition
Attribute,Value
BrowseName,ContactVariabletype
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,ContactDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the BaseDataVariableType defined in  XXXX
HasProperty,Variable,Title,LocalizedText,BaseDataVariable,Mandatory
HasProperty,Variable,GivenName,LocalizedText,BaseDataVariable,Mandatory
HasProperty,Variable,FamilyName,LocalizedText,BaseDataVariable,Mandatory
HasProperty,Variable,PhoneNumber,String,BaseDataVariable,Mandatory
HasProperty,Variable,Email,LocalizedText,BaseDataVariable,Mandatory
HasProperty,Variable,AltPhoneNumber,String,BaseDataVariable,Mandatory
HasProperty,Variable,AltEmail,LocalizedText,BaseDataVariable,Mandatory

This is an example of a possible Company sub-type. It is used in examples since it provides more information and is more typical of what an actual user would require.

Table 138 - TypicalCompanyType Type definition
Attribute,Value
BrowseName,TypicalCompanyType
IsAbstract,False
ValueRank,0 (OneOrMoreDimensions)
DataType,BaseDataType
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the CompanyType defined in  XXXX
HasComponent,Variable,PrimaryContact,ContactDataType,ContactVariableType,Mandatory
HasComponent,Variable,PrimaryAddress,AddressDataType,AddressVariableType,Mandatory
HasComponent,Variable,SalesContact,ContactDataType,ContactVariableType,Mandatory
HasComponent,Variable,ServiceContact,ContactDataType,ContactVariableType,Mandatory
HasComponent,Variable,PurchasingContact,ContactDataType,ContactVariableType,Mandatory
HasComponent,Variable,AlternateAddress,AddressDataType,AddressVariableType,Optional
HasComponent,Variable,WEBSite,String,Property,Mandatory

Annex F UML notation used in ISA-95  (Informative)

The ISA-95 object models are illustrated using the Unified Modelling Language (UML) notational methodology, as defined in ISA/IEC 19501.

Table 139 - UML notation used in ISA-95
Symbol Name,Symbol,Definition
UMLPackage,,"Defines a package, a collection of object models, state models, use cases, and other UML models. Packages are general-purpose grouping mechanisms used to organize semantically related model elements. In this standard a package is used to specify an external model, such as a production rule model, or a reference to another part of the model."
UMLClass,,"Represents a UML class of objects, each with the same types of attributes. Each object is uniquely identifiable or enumerable. No operations or methods are listed for the classes."
UMLAssociation,,"An association between elements of a class and elements of another or the same class. Each association is identified. May have the expected number or range of members of the subclass, when 'n' indicates an indeterminate number. For example, 0..n means that zero or more members of the subclass may exist."
UMLGeneralization,,Generalization (arrow points to the super class) shows that an element of the class is a specialized type of the super class.
UMLDependence,,Dependence is a weak association that shows that a modelling element depends on another modelling element. The item at the tail depends on the item at the head of the relationship.
UMLAggregation,,Aggregation (made up of) shows that an element of the class is made up of elements of other classes.
UMLCompositie,,"Composite shows a strong form of aggregation, which requires that a part instance be included in at most one composite at a time and that the composite object has sole responsibility for disposition of its parts."

Annex G Notation Extensions

Overview

The definition of the notation used in figures in this standard is described in OPC 10000-3. The following section describes some extension to this notation to allow for the illustration of structured DataTypes

Node Type Notation

DataTypeElement graphical extension is represented by the graphical form defined in Table 140

Table 140 - Notation of Nodes depending on the NodeClass
NodeClass,Graphical Representation,Comment
DataTypeElement,,Gray pentagon including text representing the string-part of the DisplayName of the DataTypeElement.

Reference Notation


        Table 141 defines an extension that illustrates the elements that are part of a DataType.

Table 141 - Simple Notation of Nodes depending on the NodeClass
ReferenceType,Graphical Representation,Comment
DataItem,,This construct is used to link a DataType to the DataTypeElement that the structured data type is composed of.

