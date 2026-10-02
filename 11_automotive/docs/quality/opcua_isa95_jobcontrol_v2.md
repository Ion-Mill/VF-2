SPDX-FileCopyrightText: Copyright (C) 2026 OPC Foundation, Inc.
SPDX-License-Identifier: LicenseRef-OPC-Specification-1.15
License: https://opcfoundation.org/license/specifications/1.15/

OPC-10031-4: OPC UA for ISA-95 - Part 4: Job Control
Version: 2.00.0
Published: 2024-01-31

1 Scope

This document defines the OPC UA companion specification for ISA-95 Job Orders, ISA-95 Job Responses, and access to queued, executing, and completed job order status and responses. 

Version 2.0 of this specification has been updated with breaking changes; in that it is not compatible with version 1.0 of the specification. Thus, this specification defines a new namespace, allowing an older application to support both models if required.

2 Normative References

The following referenced documents are indispensable for the application of this standard. For dated references, only the edition cited applies. For undated references, the latest edition of the referenced document (including any amendments) applies.

OPC 10000-1, OPC UA Specification - Part 1: Overview and Concepts


        http://www.opcfoundation.org/documents/10000-1/
      

OPC 10000-3, OPC Unified Architecture - Part 3: Address Space Model


        http://www.opcfoundation.org/documents/10000-3/
      

OPC 10000-4, OPC Unified Architecture - Part 4: Services


        http://www.opcfoundation.org/documents/10000-4/
      

OPC 10000-5, OPC Unified Architecture - Part 5: Information Model


        http://www.opcfoundation.org/documents/10000-5/
      

OPC 10000-6, OPC Unified Architecture - Part 6: Mappings


        http://www.opcfoundation.org/documents/10000-6/
      

OPC 10000-7, OPC Unified Architecture - Part 7: Profiles


        http://www.opcfoundation.org/documents/10000-7/
      

OPC 10000-16, OPC Unified Architecture - Part 16: State Machines


        http://www.opcfoundation.org/documents/10000-16/ 

ISA-95 Part 3: ANSI/ISA-95.00.03-2013 (IEC 62264-3 Modified) Enterprise-Control System Integration - Part 3: Activity Models of Manufacturing Operations Management


        https://www.isa.org/products/ansi-isa-95-00-03-2013-enterprise-control-system-i (https://www.isa.org/products/ansi-isa-95-00-03-2013-enterprise-control-system-i)  

3 Terms, abbreviated terms, and conventions

3.1 Overview

It is assumed that basic concepts of OPC UA information modelling are understood in this specification. This specification will use these concepts to describe the ISA-95 object models. The concepts and terms used to describe the OPC UA Information models are defined in other parts and listed in the following sections. Note that OPC UA terms and terms defined in this standard are italicized in the specification.

For the purposes of this document, the terms and definitions given in OPC 10000-1 and OPC 10000-3 as well as the following apply.

3.2 OPC UA for ISA-95 Terms

3.2.1 Job Order Receiver

An OPC UA server that implements methods to receive Job Orders and processes the associated job orders.

3.2.2 Job Response Provider

An OPC UA server that implements methods to provide Job Responses and returns a Job Response to the method caller. 

3.2.3 Job Response Receiver

An OPC UA server that implements methods to receive Job Responses and accepts an unsoliciated Job Response from the method caller. 

3.3 Abbreviated terms

PLC,Programmable Logic Controllers
DCS,Distributed Control Systems

3.4 Conventions used in this document

3.4.1 Conventions for Node descriptions

3.4.1.1 Node definitions


              Node definitions are specified using tables (see Table 2).


              Attributes are defined by providing the Attribute name and a value, or a description of the value.


              References are defined by providing the ReferenceType name, the BrowseName of the TargetNode and its NodeClass.

- If the TargetNode is a component of the Node being defined in the table the Attributes of the composed Node are defined in the same row of the table. 
- The DataType is only specified for Variables; "[<number>]" indicates a single-dimensional array, for multi-dimensional arrays the expression is repeated for each dimension (e.g. [2][3] for a two-dimensional array). For all arrays the ArrayDimensions is set as identified by <number> values. If no <number> is set, the corresponding dimension is set to 0, indicating an unknown size. If no number is provided at all the ArrayDimensions can be omitted. If no brackets are provided, it identifies a scalar DataType and the ValueRank is set to the corresponding value (see OPC 10000-3). In addition, ArrayDimensions is set to null or is omitted. If it can be Any or ScalarOrOneDimension, the value is put into "{<value>}", so either "{Any}" or "{ScalarOrOneDimension}" and the ValueRank is set to the corresponding value (see OPC 10000-3) and the ArrayDimensions is set to null or is omitted. Examples are given in Table 1.

Table 1 - Examples of DataTypes
Notation,Data­Type,Value­Rank,Array­Dimensions,Description
0:Int32,0:Int32,-1,omitted or null,A scalar Int32.
0:Int32[],0:Int32,1,omitted or {0},Single-dimensional array of Int32 with an unknown size.
0:Int32[][],0:Int32,2,"omitted or {0,0}",Two-dimensional array of Int32 with unknown sizes for both dimensions.
0:Int32[3][],0:Int32,2,"{3,0}",Two-dimensional array of Int32 with a size of 3 for the first dimension and an unknown size for the second dimension.
0:Int32[5][3],0:Int32,2,"{5,3}",Two-dimensional array of Int32 with a size of 5 for the first dimension and a size of 3 for the second dimension.
0:Int32{Any},0:Int32,-2,omitted or null,An Int32 where it is unknown if it is scalar or array with any number of dimensions.
0:Int32{ScalarOrOneDimension},0:Int32,-3,omitted or null,An Int32 where it is either a single-dimensional array or a scalar.

- The TypeDefinition is specified for Objects and Variables.
- The TypeDefinition column specifies a symbolic name for a NodeId, i.e. the specified Node points with a HasTypeDefinition Reference to the corresponding Node.
- The ModellingRule of the referenced component is provided by specifying the symbolic name of the rule in the ModellingRule column. In the AddressSpace, the Node shall use a HasModellingRule Reference to point to the corresponding ModellingRule Object.

If the NodeId of a DataType is provided, the symbolic name of the Node representing the DataType shall be used. 

Note that if a symbolic name of a different namespace is used, it is prefixed by the NamespaceIndex (see 3.4.2.2).


              Nodes of all other NodeClasses cannot be defined in the same table; therefore, only the used ReferenceType, their NodeClass and their BrowseName are specified. A reference to another part of this document points to their definition.


              Table 2 illustrates the table. If no components are provided, the DataType, TypeDefinition and Other columns may be omitted and only a Comment column is introduced to point to the Node definition.

Table 2 - Type Definition Table
Attribute,Value
Attribute name,"Attribute value. If it is an optional Attribute that is not set ""--"" is used."
,
References,NodeClass,BrowseName,DataType,TypeDefinition,Other
ReferenceType name,NodeClass of the target Node.,BrowseName of the target Node.,"DataType of the referenced Node, only applicable for Variables.","TypeDefinition of the referenced Node, only applicable for Variables and Objects.",Additional characteristics of the TargetNode such as the ModellingRule or AccessLevel.
NOTE Notes referencing footnotes of the table content.

Components of Nodes can be complex that is containing components by themselves. The TypeDefinition, NodeClass and DataType can be derived from the type definitions, and the symbolic name can be created as defined in 3.4.3.1. Therefore, those containing components are not explicitly specified; they are implicitly specified by the type definitions.

The Other column defines additional characteristics of the Node. Examples of characteristics that can appear in this column are show in Table 3.

Table 3 - Examples of Other Characteristics
Name,Short Name,Description
0:Mandatory,M,The Node has the Mandatory ModellingRule.
0:Optional,O,The Node has the Optional ModellingRule.
0:MandatoryPlaceholder,MP,The Node has the MandatoryPlaceholder ModellingRule.
0:OptionalPlaceholder,OP,The Node has the OptionalPlaceholder ModellingRule.
ReadOnly,RO,The Node AccessLevel has the CurrentRead bit set but not the CurrentWrite bit.
ReadWrite,RW,The Node AccessLevel has the CurrentRead and CurrentWrite bits set.
WriteOnly,WO,The Node AccessLevel has the CurrentWrite bit set but not the CurrentRead bit.

If multiple characteristics are defined they are separated by commas. The name or the short name may be used.

3.4.1.2 Additional References

To provide information about additional References, the format as shown in Table 4 is used.

Table 4 - <some>Type Additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
SourceBrowsePath is always relative to the TypeDefinition. Multiple elements are defined as separate rows of a nested table.,ReferenceType name,True = forward Reference.,"TargetBrowsePath points to another Node, which can be a well-known instance or a TypeDefinition. You can use BrowsePaths here as well, which is either relative to the TypeDefinition or absolute. If absolute, the first entry needs to refer to a type or well-known instance, uniquely identified within a namespace by the BrowseName."


              References can be to any other Node.

3.4.1.3 Additional sub-components

To provide information about sub-components, the format as shown in Table 5 is used.

Table 5 - <some>Type Additional Subcomponents
BrowsePath,References,NodeClass,BrowseName,DataType,TypeDefinition,Others
BrowsePath is always relative to the TypeDefinition. Multiple elements are defined as separate rows of a nested table,NOTE Same as for Table 2

3.4.1.4 Additional Attribute values

The type definition table provides columns to specify the values for required Node Attributes for InstanceDeclarations. To provide information about additional Attributes, the format as shown in Table 6 is used.

Table 6 - <some>Type Attribute values for child Nodes
BrowsePath,<Attribute name> Attribute
BrowsePath is always relative to the TypeDefinition. Multiple elements are defined as separate rows of a nested table,"The values of attributes are converted to text by adapting the reversible JSON encoding rules defined in OPC 10000-6.  If the JSON encoding of a value is a JSON string or a JSON number then that value is entered in the value field. Double quotes are not included. If the DataType includes a NamespaceIndex (QualifiedNames, NodeIds or ExpandedNodeIds) then the notation used for BrowseNames is used. If the value is an Enumeration the name of the enumeration value is entered. If the value is a Structure then a sequence of name and value pairs is entered. Each pair is followed by a newline. The name is followed by a colon. The names are the names of the fields in the DataTypeDefinition. If the value is an array of non-structures then a sequence of values is entered where each value is followed by a newline. If the value is an array of Structures or a Structure with fields that are arrays or with nested Structures then the complete JSON array or JSON object is entered. Double quotes are not included."

There can be multiple columns to define more than one Attribute.

3.4.2 NodeIds and BrowseNames

3.4.2.1 NodeIds

The NodeIds of all Nodes described in this standard are only symbolic names. Annex A defines the actual NodeIds.

The symbolic name of each Node defined in this document is its BrowseName, or, when it is part of another Node, the BrowseName of the other Node, a ".", and the BrowseName of itself. In this case "part of" means that the whole has a HasProperty or HasComponent Reference to its part. Since all Nodes not being part of another Node have a unique name in this document, the symbolic name is unique.

The NamespaceUri for all NodeIds defined in this document is defined in Annex A. The NamespaceIndex for this NamespaceUri is vendor-specific and depends on the position of the NamespaceUri in the server namespace table.

Note that this document not only defines concrete Nodes, but also requires that some Nodes shall be generated, for example one for each Session running on the Server. The NodeIds of those Nodes are Server-specific, including the namespace. But the NamespaceIndex of those Nodes cannot be the NamespaceIndex used for the Nodes defined in this document, because they are not defined by this document but generated by the Server.

3.4.2.2 BrowseNames

The text part of the BrowseNames for all Nodes defined in this document is specified in the tables defining the Nodes. The NamespaceUri for all BrowseNames defined in this document is defined in 8.2.

For InstanceDeclarations of NodeClass Object and Variable that are placeholders (OptionalPlaceholder and MandatoryPlaceholder ModellingRule), the BrowseName and the DisplayName are enclosed in angle brackets (<>) as recommended in OPC 10000-3.If the BrowseName is not defined by this document, a namespace index prefix is added to the BrowseName (e.g., prefix '0' leading to '0:EngineeringUnits'). This is typically necessary if a Property of another specification is overwritten or used in the OPC UA types defined in this document. Table 93 provides a list of namespaces and their indexes as used in this document.

3.4.3 Common Attributes

3.4.3.1 General

The Attributes of Nodes, their DataTypes and descriptions are defined in OPC 10000-3. Attributes not marked as optional are mandatory and shall be provided by a Server. The following tables define if the Attribute value is defined by this document or if it is server-specific.

For all Nodes specified in this document, the Attributes named in Table 7 shall be set as specified in the table.

Table 7 - Common Node Attributes
Attribute,Value
DisplayName,"The DisplayName is a LocalizedText. Each Server shall provide the DisplayName identical to the BrowseName of the Node for the LocaleId ""en"". Whether the server provides translated names for other LocaleIds are server-specific."
Description,Optionally a server-specific description is provided.
NodeClass,Shall reflect the NodeClass of the Node.
NodeId,The NodeId is described by BrowseNames as defined in 3.4.2.1.
WriteMask,"Optionally the WriteMask Attribute can be provided. If the WriteMask Attribute is provided, it shall set all non-server-specific Attributes to not writable. For example, the Description Attribute may be set to writable since a Server may provide a server-specific description for the Node. The NodeId shall not be writable, because it is defined for each Node in this document."
UserWriteMask,Optionally the UserWriteMask Attribute can be provided. The same rules as for the WriteMask Attribute apply.
RolePermissions,Optionally server-specific role permissions can be provided.
UserRolePermissions,Optionally the role permissions of the current Session can be provided. The value is server-specific and depends on the RolePermissions Attribute (if provided) and the current Session.
AccessRestrictions,Optionally server-specific access restrictions can be provided.

3.4.3.2 Objects

For all Objects specified in this document, the Attributes named in Table 8 shall be set as specified in the Table 8. The definitions for the Attributes can be found in OPC 10000-3.

Table 8 - Common Object Attributes
Attribute,Value
EventNotifier,Whether the Node can be used to subscribe to Events or not is server-specific.

3.4.3.3 Variables

For all Variables specified in this document, the Attributes named in Table 9 shall be set as specified in the table. The definitions for the Attributes can be found in OPC 10000-3.

Table 9 - Common Variable Attributes
Attribute,Value
MinimumSamplingInterval,"Optionally, a server-specific minimum sampling interval is provided."
AccessLevel,"The access level for Variables used for type definitions is server-specific, for all other Variables defined in this document, the access level shall allow reading; other settings are server-specific."
UserAccessLevel,The value for the UserAccessLevel Attribute is server-specific. It is assumed that all Variables can be accessed by at least one user.
Value,"For Variables used as InstanceDeclarations, the value is server-specific; otherwise it shall represent the value described in the text."
ArrayDimensions,If the ValueRank does not identify an array of a specific dimension (i.e. ValueRank <= 0) the ArrayDimensions can either be set to null or the Attribute is missing. This behaviour is server-specific. If the ValueRank specifies an array of a specific dimension (i.e. ValueRank > 0) then the ArrayDimensions Attribute shall be specified in the table defining the Variable.
Historizing,The value for the Historizing Attribute is server-specific.
AccessLevelEx,"If the AccessLevelEx Attribute is provided, it shall have the bits 8, 9, and 10 set to 0, meaning that read and write operations on an individual Variable are atomic, and arrays can be partly written."

3.4.3.4 VariableTypes

For all VariableTypes specified in this document, the Attributes named in Table 10 shall be set as specified in the table. The definitions for the Attributes can be found in OPC 10000-3.

Table 10 - Common VariableType Attributes
Attributes,Value
Value,Optionally a server-specific default value can be provided.
ArrayDimensions,If the ValueRank does not identify an array of a specific dimension (i.e. ValueRank <= 0) the ArrayDimensions can either be set to null or the Attribute is missing. This behaviour is server-specific. If the ValueRank specifies an array of a specific dimension (i.e. ValueRank > 0) then the ArrayDimensions Attribute shall be specified in the table defining the VariableType.

3.4.3.5 Methods

For all Methods specified in this document, the Attributes named in Table 11 shall be set as specified in the table. The definitions for the Attributes can be found in OPC 10000-3.

Table 11 - Common Method Attributes
Attributes,Value
Executable,"All Methods defined in this document shall be executable (Executable Attribute set to ""True""), unless it is defined differently in the Method definition."
UserExecutable,The value of the UserExecutable Attribute is server-specific. It is assumed that all Methods can be executed by at least one user.

4 ISA-95 Overview

For OPC UA users that may not be familiar with ISA 95 Part 4 Job Orders the following section provides a brief overview of key elements of job order management. 

4.1 Job Order

ISA 95 defines a Job Order as a request for a unit of work to be executed. Typically, these are the lowest level scheduled objects in a work schedule, as shown in Figure 1. In ISA 95 a Work Schedule defines all the activities to be accomplished to meet a production request (or production order). A Work Schedule is made up of one or more Work Requests, depending on how the work is to be split, such as one order for packaging of 1,000,000 bottles, to be executed as 4 separate work requests of 250,000 bottles each. Each Work Request is made up of one or more Job Orders which define the work to be done in a work center (such as a packaging line or production line). 

[Figure: Figure 1 - Work Schedule, Work Request, and Job Orders]


          Job Orders have a procedure or workflow that is followed, either automatically or manually. Typical Job Orders in serialization are packaging orders for specific products. The Job Order contains all the variable information about the job order, such as quantity to be packaged, various values to be printed on labels, and any options, such as inserts to be added or case packing options. Each Job Order identifies a Work Master to be used. Work Master is the ISA 95 term for the procedure that is to be followed. Examples of Work Masters include ISA 88 Master Recipes or ISA 95 Workflow Procedures.


          Job Orders are often sent from Level 3 MES/MOM systems to batch execution systems, automation systems (PLCs and DCSs), or workflow systems for manual operations. An often-used implementation is to have an ERP or MES sent Job Orders to specific parts of production. In Figure 1, for example a production line is executing one set of Job Orders, a packaging line is executing another set, synchronized with the production line, a palletizing line, synchronized with the packaging line, an AGV (Automated Guided Vehicle) system that executes a job to move materials from the palletizer to a AWS (Automated Warehouse System). Each of these systems perform independent job, with their own local Work Masters and workflows.

A Job Order contains values for job specific parameters (such as "Use By Dates" to be applied to labels), material requirements (such as an identification and quantity of the material lot to be produced), equipment requirements (such as which packaging line to use), personnel requirements for the job order (such as training requirements), and physical asset requirements (such as which testing equipment to use).

4.2 Job Order Information Model

The information objects identified in Figure 2 are used to describe a Job Order. This is a subset of the ISA 95 Part 4, Edition 2 Job Order model, intended to meet a large percentage of situations where nested resource requirements and external linkages are not needed. See the ISA 95 Part 4 specification for details on the attributes and relationships. 

[Figure: Figure 2 - Job Order Information Model]


          Job Order - The specification of a job to be executed.


          Job Order Parameter - Additional information associated with the Job Order is represented in name/value pairs and defined Job Order Parameters.


          Personnel Requirement - Information associated with the Job Order that defines additional personnel and/or person requirements. 


          Equipment Requirement - Information associated with the Job Order that defines additional equipment class and/or equipment requirements.


          Physical Asset Requirement - Information associated with the Job Order that defines additional physical asset class and/or physical asset requirements.


          Material Requirement - Information associated with the Job Order that defines additional material class, material definition, material lot, and/or material sublot requirements.

See Annex C for examples of Job Orders. 

Note that the data types and enumerations used in this companion specification use the ISA 95 names, with the ISA95 prefix. 

4.3 Job Response

A Job Response is a report on work done for a Job Order. The information objects identified in Figure 3 are used to describe a Job Response. This is a subset of the ISA 95 Part 4, Edition 2 Job Response model, intended to meet a large percentage of situations where nested resource actuals and external linkages are not needed. See the ISA 95 Part 4 specification for details on the attributes and relationships.

[Figure: Figure 3 - Job Response Information Model]


          Job Response - The report on the execution of a Job Order.


          Job Response Data - Additional information associated with the Job response is represented in name/value pairs and defined Job Response Data.


          Personnel Actual - Information associated with the Job Response that defines additional personnel and/or person actuals.


          Equipment Actual - Information associated with the Job Response that defines additional equipment class and/or equipment actuals.


          Physical Asset Actual - Information associated with the Job Response that defines additional physical asset class and/or physical asset actuals.


          Material Actual - Information associated with the Job Response that defines additional material class, material definition, material lot, and/or material sublot actuals.

5 Modelling Approach of ISA-95

The modelling approach for generating a UA model from the ANSI/ISA-95 Part 3 specification follows the following general concepts.

An OPC UA server may support the activity of receiving unsolicited Job Orders for processing.

An OPC UA server may support the activity of receiving unsolicited requests for Job Responses.

An OPC UA server may support the activity of receiving unsolicited Job Responses.

Data types from the ISA-95 model are mapped to OPC UA DataTypes (i.e. strings if localized are mapped to LocalizedText).

6 ISA-95 Data Representation Model

6.1 General

The OPC UA ISA-95 Information Model is a representation of the ISA-95 data model in OPC Methods, ObjectTypes, VariableTypes, DataTypes and ReferenceTypes.

This model generates standard types. All ISA-95 types will be defined in their own namespace and will begin with "ISA95" 

The following conventions apply to ObjectType, VariableType and DataType naming:

All ObjectTypes include "ObjectType" as part of the name

All DataTypes that are structures include "DataType" as part of the name, this is to be able to differentiate them from any VariableTypes that will just end in Type.

All enumerations will end in "Enum", to clearly identify that it is an enumeration.

All base DataTypes (int32, float, …) used in the OPC UA server will be those defined in OPC UA, see OPC 10000-6 for more detail on the representation of the datatypes. 

6.2 ObjectTypes

6.2.1 ISA95JobOrderReceiverObjectType

6.2.1.1 Overview

The ISA95JobOrderReceiverObjectType contains methods to receive job order commands and optional definitions of allowable job order information as illustrated in Figure 4.

[Figure: Figure 4 - Job Order Receiver Object Type Methods and Data]

In addition, it provides information about the StateMachine of the job orders managed by instances of the ObjectType. As the job orders are not represented as Objects in the AddressSpace, but just as structured values, this ObjectType only provides the meta data of the StateMachine. It may be subtyped to add additional substates.

In Figure 5, an overview of the states is given. Note that this ObjectType does not define the substates of NotAllowedToStart, AllowedToStart, Ended and Interrupted. This is done in the ISA95JobOrderStateMachineType, defined in 6.2.2. The dotted states and transitions are not represented in the StateMachine at all. They express how job orders are added and removed from the system (InitialState and EndState and their transitions) and a logical state (Prepared) which is always exposed by its subtypes NotAllowedToStart and AllowedToStart.

[Figure: Figure 5 - States of a Job Order]

A job order is added to the system by calling the Store or StoreAndStart Method defined on the ISA95JobOrderReceiverObjectType or by some internal mechanisms. Afterwards, the job order is in the state NotAllowedToStart or AllowedToStart. In both states, the job order is not executed. Using the Update Method, the job order may still be changed. Calling the Start Method switches the state from NotAllowedToStart to AllowedToStart, and calling RevokeStart vice versa.

When a job order is in the state AllowedToStart, the system may automatically start the job order depending on available recourses and priorities in case several job orders are in the same state. If the AllowedToStart state provides substates, they may indicate if a job order can be started (e.g. Waiting indicates that it cannot be started).

When the job order starts to be executed, it switches its state to Running.


              Clients may interrupt a running job order by calling the Pause Method. The system may also automatically interrupt the job order. In both cases, the state switches to Interrupted. Substates may indicate if the interruption was triggered from external (Suspended) or automatic (Held).


              Clients may resume the execution of an interrupted job by calling the Resume Method, or the system may automatically continue. In both cases, the state switches back to Running.

A job order may be aborted by calling the Abort Method. This can be done while the job order is running, interrupted or not even started (AllowedToStart and NotAllowedToStart). In all cases, the state switches to Aborted.

When the job order was executed, it automatically switches in the state Ended. Substates of Ended may expose whether some postprocessing needs to be done before receiving the final results of the execution.

Some job orders may not be defined to finish its execution automatically. In addition, some job orders may get stopped before the planned amount of the job order is produced. In both cases, the Stop Method is called to end the execution of the job order. This can either be done while in Running or in Interrupted. In both cases, it switches into Ended.

When the job order is either Aborted or Ended, the job order may be deleted from the system by calling the Clear Method. This is typically done by a specific Client after the Client has received the final results of the job order execution.

A job order that has not been started (AllowedToStart or NotAllowedToStart) may be removed from the system before execution by calling the Cancel Method.

6.2.1.2 TypeDefinition

The ObjectType is formally defined in Table 12. Note that the transitions do not expose causes as the StateMachine is not used on an individual Object exposing its state, but just as meta data for values.

Table 12 - ISA95JobOrderReceiverObjectType definition
Attribute,Value
BrowseName,ISA95JobOrderReceiverObjectType
IsAbstract,False
References,Node Class,BrowseName,DataType,TypeDefinition,Other
"Subtype of the 0:FiniteStateMachineType defined in OPC 10000-16, i.e. inheriting the InstanceDeclarations of that Node."
0:HasComponent,Method,Store,,See 6.2.1.3,O
0:HasComponent,Method,StoreAndStart,,See 6.2.1.4,O
0:HasComponent,Method,Start,,See 6.2.1.5,O
0:HasComponent,Method,Update,,See 6.2.1.9,O
0:HasComponent,Method,Abort,,See 6.2.1.10,O
0:HasComponent,Method,Stop,,See 6.2.1.10,O
0:HasComponent,Method,Cancel,,See 6.2.1.12,O
0:HasComponent,Method,Clear,,See 6.2.1.13,O
0:HasComponent,Method,Pause,,See 6.2.1.7,O
0:HasComponent,Method,Resume,,See 6.2.1.8,O
0:HasComponent,Method,RevokeStart,,See 6.2.1.6,O
0:HasProperty,Variable,MaxDownloadableJobOrders,0:UInt16,0:PropertyType,"M,RO"
0:HasComponent,Variable,JobOrderList,ISA95JobOrderAndStateDataType[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,WorkMaster,ISA95WorkMasterDataType[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,MaterialClassID,0:String[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,MaterialDefinitionID,0:String[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,EquipmentID,0:String[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,PhysicalAssetID,0:String[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Variable,PersonnelID,0:String[],0:BaseDataVariableType,"M,RO"
0:HasComponent,Object,NotAllowedToStart,,0:StateType,
0:HasComponent,Object,AllowedToStart,,0:StateType,
0:HasComponent,Object,Running,,0:StateType,
0:HasComponent,Object,Interrupted,,0:StateType,
0:HasComponent,Object,Ended,,0:StateType,
0:HasComponent,Object,Aborted,,0:StateType,
0:HasComponent,Object,FromNotAllowedToStartToNotAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromNotAllowedToStartToAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToNotAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToRunning,,0:TransitionType,
0:HasComponent,Object,FromRunningToInterrupted,,0:TransitionType,
0:HasComponent,Object,FromRunningToEnded,,0:TransitionType,
0:HasComponent,Object,FromRunningToAborted,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToAborted,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToRunning,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToEnded,,0:TransitionType,
0:HasComponent,Object,FromNotAllowedToStartToAborted,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToAborted,,0:TransitionType,
Conformance Units
ISA-95 Job Order Receiver V2


The components of the ObjectType have additional references which are defined in Table 13.

Table 13 - ISA95JobOrderReceiverObjectType additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
FromNotAllowedToStartToNotAllowedToStart,0:FromState,True,NotAllowedToStart
,0:ToState,True,NotAllowedToStart
,0:HasCause,True,Update
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromNotAllowedToStartToAllowedToStart,0:FromState,True,NotAllowedToStart
,0:ToState,True,AllowedToStart
,0:HasCause,True,Start
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToNotAllowedToStart,0:FromState,True,AllowedToStart
,0:ToState,True,NotAllowedToStart
,0:HasCause,True,RevokeStart
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToAllowedToStart,0:FromState,True,AllowedToStart
,0:ToState,True,AllowedToStart
,0:HasCause,True,Update
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToRunning,0:FromState,True,AllowedToStart
,0:ToState,True,Running
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToInterrupted,0:FromState,True,Running
,0:ToState,True,Interrupted
,0:HasCause,True,Pause
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToEnded,0:FromState,True,Running
,0:ToState,True,Ended
,0:HasCause,True,Stop
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToAborted,0:FromState,True,Running
,0:ToState,True,Aborted
,0:HasCause,True,Abort
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToAborted,0:FromState,True,Interrupted
,0:ToState,True,Aborted
,0:HasCause,True,Abort
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToRunning,0:FromState,True,Interrupted
,0:ToState,True,Running
,0:HasCause,True,Resume
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToEnded,0:FromState,True,Interrupted
,0:ToState,True,Ended
,0:HasCause,True,Stop
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromNotAllowedToStartToAborted,0:FromState,True,NotAllowedToStart
,0:ToState,True,Aborted
,0:HasCause,True,Abort
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToAborted,0:FromState,True,AllowedToStart
,0:ToState,True,Aborted
,0:HasCause,True,Abort
,0:HasEffect,True,ISA95JobOrderStatusEventType

The component Variables of the ISA95JobOrderReceiverObjectType have additional Attributes defined in Table 14.

Table 14 - ISA95JobOrderReceiverObjectType Attribute values for child Nodes
BrowsePath,Value Attribute,Description
NotAllowedToStart,,The job order is stored but may not be executed.
"NotAllowedToStart
0:StateNumber",1,
AllowedToStart,,The job order is stored and may be executed.
"AllowedToStart
0:StateNumber",2,
Running,,The job order is executing.
"Running
0:StateNumber",3,
Interrupted,,The job order has been temporarily stopped.
"Interrupted
0:StateNumber",4,
Ended,,The job order has been completed and is no longer in execution.
"Ended
0:StateNumber",5,
Aborted,,The job order is aborted.
"Aborted
0:StateNumber",6,
FromNotAllowedToStartToNotAllowedToStart,,This transition is triggered when the Update Method is called and the job order is modified.
"FromNotAllowedToStartToNotAllowedToStart
0:TransitionNumber",1,
FromNotAllowedToStartToAllowedToStart,,This transition is triggered when the Start Method is called.
"FromNotAllowedToStartToAllowedToStart
0:TransitionNumber",2,
FromAllowedToStartToNotAllowedToStart,,This transition is triggered when the RevokeStart Method is called.
"FromAllowedToStartToNotAllowedToStart
0:TransitionNumber",3,
FromAllowedToStartToAllowedToStart,,This transition is triggered when the Update Method is called and the job order is modified.
"FromAllowedToStartToAllowedToStart
0:TransitionNumber",4,
FromAllowedToStartToRunning,,This transition is triggered when a job order is started to be executed.
"FromAllowedToStartToRunning
0:TransitionNumber",5,
FromRunningToInterrupted,,"This transition is triggered when an executing job order gets interrupted, either internally or by the Pause Method."
"FromRunningToInterrupted
0:TransitionNumber",6,
FromRunningToEnded,,"This transition is triggered when the execution of a job order has finished, either internally or by the Stop Method."
"FromRunningToEnded
0:TransitionNumber",7,
FromRunningToAborted,,This transition is triggered when Abort Method is called.
"FromRunningToAborted
0:TransitionNumber",8,
FromInterruptedToAborted,,This transition is triggered when Abort Method is called.
"FromInterruptedToAborted
0:TransitionNumber",9,
FromInterruptedToRunning,,This transition is triggered when Resume Method is called.
"FromInterruptedToRunning
0:TransitionNumber",10,
FromInterruptedToEnded,,This transition is triggered when Stop Method is called.
"FromInterruptedToEnded
0:TransitionNumber",11,
FromNotAllowedToStartToAborted,,This transition is triggered when Abort Method is called.
"FromNotAllowedToStartToAborted
0:TransitionNumber",12,
FromAllowedToStartToAborted,,This transition is triggered when Abort Method is called.
"FromAllowedToStartToAborted
0:TransitionNumber",13,


              
                JobOrderList
               - Defines a read-only list of job order information available from the server. The information returned is defined by the server and may be a complete copy of a received job order or may be just the IDs and the state of the job orders. If there are no job orders available from the server, then this may be null.


              
                MaxDownloadableJobOrders
               - Defines the maximum number of job orders that can be managed at the same time. As all managed job orders are accessible in the JobOrderList, it restricts the length of that array. Max of UInt16 indicates, that there is no limit.


              
                WorkMaster
               - Defines a read-only set of work master IDs that may be specified in a job order, and the read-only set of parameters that may be specified for a specific work master. If there are no restrictions on what work master IDs can be sent with a job order, then this may be null. 

Recipes associated with the job order are identified using the WorkMasterID. The ID in the ISA95WorkMasterDataType is an identification of the Work Master and can be internal identifications, NodeIds, web links, or a client and server agreed to format.


              
                MaterialClassID
               - Defines a read-only set of Material Classes IDs that may be specified in a job order. If there are no restrictions on what Material Classes IDs can be sent with a job order, then this may be null.


              
                MaterialDefinitionID
               - Defines a read-only set of Material Definition IDs that may be specified in a job order. If there are no restrictions on what Material Definition IDs can be sent with a job order, then this may be null.


              
                EquipmentID
               - Defines a read-only set of Equipment Class IDs and Equipment IDs that may be specified in a job order. If there are no restrictions on what Equipment IDs can be sent with a job order, then this may be null.


              
                PhysicalAssetID
               - Defines a read-only set of Physical Asset Class IDs and Physical Asset IDs that may be specified in a job order. If there are no restrictions on what Physical Asset IDs can be sent with a job order, then this may be null.


              
                PersonnelID
               - Defines a read-only set of Personnel IDs and Person IDs that may be specified in a job order. If there are no restrictions on what Personnel IDs can be sent with a job order, then this may be null.

The ObjectType inherits from the 0:FiniteStateMachineType to provide the StateMachine all job orders managed by the instances of the ObjectType support. The mandatory CurrentState inherited shall always return a BAD StatusCode, as the Object only provides the meta data of the states of the job orders provided in the JobOrderList. The ObjectType may provide be subtyped to provide SubStateMachines for specific states and also the AvailableStates and AvailableTransitions Variables may be provided to restrict the usage of the StateMachine.

6.2.1.3 Store Method

This Method receives a new job order and stores the new job order in local storage, but does not start the job order. After successful execution of the method, the JobOrderList shall have a new entry in state NotAllowedToStart.

The signature of this Method is specified below. Table 15 and Table 16 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Store (
	[in]	ISA95JobOrderDataType		JobOrder
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 15 - Store Method Arguments
Argument,Description
JobOrder,"Contains information defining the job order with all parameters and any material, equipment, or physical asset requirements associated with the job order."
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method result codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 16 - Store Method AddressSpace Definition
Attribute,Value
BrowseName,Store
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.4 StoreAndStart Method

This Method receives a new job order and stores the new job order in local storage, and start it as soon as the Job Order receiver is ready to start. After successful execution of the method, the JobOrderList shall have a new entry in state AllowedToStart. Note: the system may internally start executing the job order immediately, so potentially the job order is already in a different state when accessed the first time.

The signature of this Method is specified below. Table 17 and Table 18 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	StoreAndStart (
	[in]	ISA95JobOrderDataType		JobOrder
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 17 - StoreAndStart Method Arguments
Argument,Description
JobOrder,"Contains information defining the job order with all parameters and any material, equipment, or physical asset requirements associated with the job order."
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 18 - StoreAndStart Method AddressSpace Definition
Attribute,Value
BrowseName,StoreAndStart
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.5 Start Method

This Method starts a job order as soon as the Job Order receiver is ready to start. After successful execution of the method, job order in the JobOrderList shall be in state AllowedToStart.

If multiple job orders have been commanded to start, then the priority and timing values in the job orders shall be used to determine the order of execution of the job orders.

The signature of this Method is specified below. Table 19 and Table 20 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Start (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 19 - Start Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be started.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 20 - Start Method AddressSpace Definition
Attribute,Value
BrowseName,Start
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.6 RevokeStart Method

This Method revokes a not started job (in AllowedToStart). After successful execution of the method, job order in the JobOrderList shall be in state NotAllowedToStart.

The signature of this Method is specified below. Table 21 and Table 22 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	RevokeStart (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 21 - RevokeStart Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order where the start is revoked.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4 or Annex B Table 94, and Table 95).

Table 22 - RevokeStart Method AddressSpace Definition
Attribute,Value
BrowseName,RevokeStart
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.7 Pause Method

This Method pauses a started job. After successful execution of the method, job order in the JobOrderList shall be in state Interrupted.

The signature of this Method is specified below. Table 23 and Table 24 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Pause (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 23 - Pause Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be paused.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 24 - Pause Method AddressSpace Definition
Attribute,Value
BrowseName,Pause
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.8 Resume Method

This Method resumes an interrupted job (in state Interrupted). After successful execution of the method, job order in the JobOrderList shall be in state Running.

The signature of this Method is specified below. Table 25 and Table 26 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Resume (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 25 - Resume Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be resumed.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 26 - Resume Method AddressSpace Definition
Attribute,Value
BrowseName,Resume
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.9 Update Method

This Method updates an existing job order that has not yet been started, with the new order information. All previously stored information is replaced.

The signature of this Method is specified below. Table 27 and Table 28 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Update (
	[in]	ISA95JobOrderDataType		JobOrder
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 27 - Update Method Arguments
Argument,Description
JobOrder,"Contains information defining the job order with all parameters and any material, equipment, or physical asset requirements associated with the job order."
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 28 - Update Method AddressSpace Definition
Attribute,Value
BrowseName,Update
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.10 Abort Method

This Method aborts a job order. After successful execution of the method, job order in the JobOrderList shall be in state Aborted.

The signature of this Method is specified below. Table 29 and Table 30 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Abort (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 29 - Abort Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be aborted.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94 and Table 95).

Table 30 - Abort Method AddressSpace Definition
Attribute,Value
BrowseName,Abort
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.11 Stop Method

This Method stops a started job order. After successful execution of the method, job order in the JobOrderList shall be in state Ended.

The signature of this Method is specified below. Table 31 and Table 32 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Stop (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 31 - Stop Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be stopped.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 32 - Stop Method AddressSpace Definition
Attribute,Value
BrowseName,Stop
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.12 Cancel Method

This Method cancels a not started job order (in AllowedToStart or NotAllowedToStart) and removes the stored information. After successful execution of the method, there shall be no job order with the JobOrderID in the JobOrderList.

The signature of this Method is specified below. Table 33 and Table 34 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Cancel (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 33 - Cancel Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be canceled.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Note: This specification does not define how a client can access the last comment. It may be displayed in a local HMI or provided in the parameters of the job response.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 34 - Cancel Method AddressSpace Definition
Attribute,Value
BrowseName,Cancel
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.1.13 Clear Method

This Method clears any maintained information on the Job Order (usually sent after a receipt of a Job Response with a status of Finished.). After successful execution of the method, there shall be no job order with the JobOrderID in the JobOrderList.

Note: It is server-specific whether Job Orders get cleared by the Server automatically when it runs out of resources or after a period of time or other reasons.

The signature of this Method is specified below. Table 35 and Table 36 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	Clear (
	[in]	0:String				JobOrderID
	[in]	LocalizedText[]			Comment
	[out]	0:UInt64			   	ReturnStatus
	);

Table 35 - Clear Method Arguments
Argument,Description
JobOrderID,Identification of the Job Order to be cleared.
Comment,"The comment provides a description of why the method was called. In order to provide the comment in several languages, it is an array of LocalizedText. The array may be empty, when no comment is provided."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.


              Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 36 - Clear Method AddressSpace Definition
Attribute,Value
BrowseName,Clear
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.2 ISA95JobOrderReceiverSubStatesType

6.2.2.1 Overview

This ObjectType describes the overall state of a job order including common SubStateMachines. As the job orders are not represented as Objects in the AddressSpace, but just as structured values, this StateMachine only provides the meta data of the state machine. It may be subtyped to add additional substates.

6.2.2.2 TypeDefinition

The ObjectType formally defined in Table 37. 

Table 37 - ISA95JobOrderReceiverSubStatesType definition
Attribute,Value
BrowseName,ISA95JobOrderReceiverSubStatesType
IsAbstract,False
References,Node Class,BrowseName,DataType,TypeDefinition,Other
Subtype of the ISA95JobOrderReceiverObjectType
0:HasComponent,Object,NotAllowedToStart,,0:StateType,
0:HasComponent,Object,AllowedToStart,,0:StateType,
0:HasComponent,Object,Running,,0:StateType,
0:HasComponent,Object,Interrupted,,0:StateType,
0:HasComponent,Object,Ended,,0:StateType,
0:HasComponent,Object,Aborted,,0:StateType,
0:HasComponent,Object,FromNotAllowedToStartToNotAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromNotAllowedToStartToAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToNotAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToAllowedToStart,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToRunning,,0:TransitionType,
0:HasComponent,Object,FromRunningToInterrupted,,0:TransitionType,
0:HasComponent,Object,FromRunningToEnded,,0:TransitionType,
0:HasComponent,Object,FromRunningToAborted,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToAborted,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToRunning,,0:TransitionType,
0:HasComponent,Object,FromInterruptedToEnded,,0:TransitionType,
0:HasComponent,Object,FromNotAllowedToStartToAborted,,0:TransitionType,
0:HasComponent,Object,FromAllowedToStartToAborted,,0:TransitionType,
0:HasComponent,Object,NotAllowedToStartSubstates,,ISA95PrepareStateMachineType,O
0:HasComponent,Object,AllowedToStartSubstates,,ISA95PrepareStateMachineType,O
0:HasComponent,Object,EndedSubstates,,ISA95EndedStateMachineType,O
0:HasComponent,Object,InterruptedSubstates,,ISA95InterruptedStateMachineType,O
Conformance Units
ISA-95 Job Control Job Order Receiver SubStates


The components of the ObjectType have additional references which are defined in Table 38.

Table 38 - ISA95JobOrderReceiverSubStatesType additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
FromNotAllowedToStartToNotAllowedToStart,0:FromState,True,NotAllowedToStart
,0:ToState,True,NotAllowedToStart
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Update"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromNotAllowedToStartToAllowedToStart,0:FromState,True,NotAllowedToStart
,0:ToState,True,AllowedToStart
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Start"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToNotAllowedToStart,0:FromState,True,AllowedToStart
,0:ToState,True,NotAllowedToStart
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
RevokeStart"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToAllowedToStart,0:FromState,True,AllowedToStart
,0:ToState,True,AllowedToStart
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Update"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToRunning,0:FromState,True,AllowedToStart
,0:ToState,True,Running
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToInterrupted,0:FromState,True,Running
,0:ToState,True,Interrupted
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Pause"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToEnded,0:FromState,True,Running
,0:ToState,True,Ended
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Stop"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromRunningToAborted,0:FromState,True,Running
,0:ToState,True,Aborted
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Abort"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToAborted,0:FromState,True,Interrupted
,0:ToState,True,Aborted
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Abort"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToRunning,0:FromState,True,Interrupted
,0:ToState,True,Running
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Resume"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromInterruptedToEnded,0:FromState,True,Interrupted
,0:ToState,True,Ended
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Stop"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromNotAllowedToStartToAborted,0:FromState,True,NotAllowedToStart
,0:ToState,True,Aborted
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Abort"
,0:HasEffect,True,ISA95JobOrderStatusEventType
FromAllowedToStartToAborted,0:FromState,True,AllowedToStart
,0:ToState,True,Aborted
,0:HasCause,True,"ISA95JobOrderReceiverObjectType
Abort"
,0:HasEffect,True,ISA95JobOrderStatusEventType
NotAllowedToStart,0:HasSubStateMachine,True,NotAllowedToStartSubstates
AllowedToStart,0:HasSubStateMachine,True,AllowedToStartSubstates
Ended,0:HasSubStateMachine,True,EndedSubstates
Interrupted,0:HasSubStateMachine,True,InterruptedSubstates

The component Variables of the ISA95JobOrderReceiverSubStatesType have additional Attributes defined in Table 39.

Table 39 - ISA95JobOrderReceiverSubStatesType Attribute values for child Nodes
BrowsePath,Value Attribute,Description
NotAllowedToStart,,The job order is stored but may not be executed.
"NotAllowedToStart
0:StateNumber",1,
AllowedToStart,,The job order is stored and may be executed.
"AllowedToStart
0:StateNumber",2,
Running,,The job order is executing.
"Running
0:StateNumber",3,
Interrupted,,The job order has been temporarily stopped.
"Interrupted
0:StateNumber",4,
Ended,,The job order has been completed and is no longer in execution.
"Ended
0:StateNumber",5,
Aborted,,The job order is aborted.
"Aborted
0:StateNumber",6,
FromNotAllowedToStartToNotAllowedToStart,,This transition is triggered when the Update Method is called and the job order is modified.
"FromNotAllowedToStartToNotAllowedToStart
0:TransitionNumber",1,
FromNotAllowedToStartToAllowedToStart,,This transition is triggered when the Start Method is called.
"FromNotAllowedToStartToAllowedToStart
0:TransitionNumber",2,
FromAllowedToStartToNotAllowedToStart,,This transition is triggered when the RevokeStart Method is called.
"FromAllowedToStartToNotAllowedToStart
0:TransitionNumber",3,
FromAllowedToStartToAllowedToStart,,This transition is triggered when the Update Method is called and the job order is modified.
"FromAllowedToStartToAllowedToStart
0:TransitionNumber",4,
FromAllowedToStartToRunning,,This transition is triggered when a job order is started to be executed.
"FromAllowedToStartToRunning
0:TransitionNumber",5,
FromRunningToInterrupted,,"This transition is triggered when an executing job order gets interrupted, either internally or by the Pause Method."
"FromRunningToInterrupted
0:TransitionNumber",6,
FromRunningToEnded,,"This transition is triggered when the execution of a job order has finished, either internally or by the Stop Method."
"FromRunningToEnded
0:TransitionNumber",7,
FromRunningToAborted,,This transition is triggered when Abort Method is called.
"FromRunningToAborted
0:TransitionNumber",8,
FromInterruptedToAborted,,This transition is triggered when Abort Method is called.
"FromInterruptedToAborted
0:TransitionNumber",9,
FromInterruptedToRunning,,This transition is triggered when Resume Method is called.
"FromInterruptedToRunning
0:TransitionNumber",10,
FromInterruptedToEnded,,This transition is triggered when Stop Method is called.
"FromInterruptedToEnded
0:TransitionNumber",11,
FromNotAllowedToStartToAborted,,This transition is triggered when Abort Method is called.
"FromNotAllowedToStartToAborted
0:TransitionNumber",12,
FromAllowedToStartToAborted,,This transition is triggered when Abort Method is called.
"FromAllowedToStartToAborted
0:TransitionNumber",13,
NotAllowedToStartSubstates,,Substates of NotAllowedToStart
AllowedToStartSubstates,,Substates of AllowedToStart
EndedSubstates,,Substates of Ended
InterruptedSubstates,,Substates of Interrupted

6.2.3 ISA95PrepareStateMachineType

This ObjectType describes a SubStateMachine that a job order may use while already stored in the system but not being executed. The ObjectType formally defined in Table 40.

Table 40 - ISA95PrepareStateMachineType definition
Attribute,Value
BrowseName,ISA95PrepareStateMachineType
IsAbstract,False
References,Node Class,BrowseName,DataType,TypeDefinition,Other
"Subtype of the 0:FiniteStateMachineType defined in OPC 10000-16, i.e. inheriting the InstanceDeclarations of that Node."
0:HasComponent,Object,Waiting,,0:StateType,
0:HasComponent,Object,Ready,,0:StateType,
0:HasComponent,Object,Loaded,,0:StateType,
0:HasComponent,Object,FromWaitingToReady,,0:TransitionType,
0:HasComponent,Object,FromReadyToLoaded,,0:TransitionType,
0:HasComponent,Object,FromReadyToWaiting,,0:TransitionType,
0:HasComponent,Object,FromLoadedToReady,,0:TransitionType,
0:HasComponent,Object,FromLoadedToWaiting,,0:TransitionType,
Conformance Units
ISA-95 Job Control Job Order Receiver SubStates


The components of the ObjectType have additional references which are defined in Table 41.

Table 41 - ISA95PrepareStateMachineType additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
FromWaitingToReady,0:FromState,True,Waiting
,0:ToState,True,Ready
FromReadyToLoaded,0:FromState,True,Ready
,0:ToState,True,Loaded
FromReadyToWaiting,0:FromState,True,Ready
,0:ToState,True,Waiting
FromLoadedToReady,0:FromState,True,Loaded
,0:ToState,True,Ready
FromLoadedToWaiting,0:FromState,True,Loaded
,0:ToState,True,Waiting

The component Variables of the ISA95PrepareStateMachineType have additional Attributes defined in Table 42.

Table 42 - ISA95PrepareStateMachineType Attribute values for child Nodes
BrowsePath,Value Attribute,Description
Waiting,,The necessary pre-conditions have not been met and the job order is not ready to run.
"Waiting
0:StateNumber",1,
Ready,,"The necessary pre-conditions have been met and the job order is ready to run, awaiting a Start command."
"Ready
0:StateNumber",2,
Loaded,,"In situations where only one job may be in active memory and is able to be run, then the job is loaded in active memory, the necessary pre-conditions have been met, and the job order is ready to run, awaiting a Start command."
"Loaded
0:StateNumber",3,
FromWaitingToReady,,This transition is triggered when the system is ready to start the execution of the job order.
"FromWaitingToReady
0:TransitionNumber",1,
FromReadyToLoaded,,This transition is triggered when the program or configuration to execute the job order is loaded.
"FromReadyToLoaded
0:TransitionNumber",2,
FromReadyToWaiting,,This transition is triggered when the system is not ready to start the execution of the job order anymore.
"FromReadyToWaiting
0:TransitionNumber",3,
FromLoadedToReady,,This transition is triggered when the program or configuration to execute the job order is unloaded.
"FromLoadedToReady
0:TransitionNumber",4,
FromLoadedToWaiting,,This transition is triggered when the system is not ready to start the execution of the job order anymore.
"FromLoadedToWaiting
0:TransitionNumber",5,

6.2.4 ISA95EndedStateMachineType

This ObjectType describes a SubStateMachine that a job order may use after being executed. The ObjectType formally defined in Table 43.

Table 43 - ISA95EndedStateMachineType definition
Attribute,Value
BrowseName,ISA95EndedStateMachineType
IsAbstract,False
References,Node Class,BrowseName,DataType,TypeDefinition,Other
"Subtype of the 0:FiniteStateMachineType defined in OPC 10000-16, i.e. inheriting the InstanceDeclarations of that Node."
0:HasComponent,Object,Completed,,0:StateType,
0:HasComponent,Object,Closed,,0:StateType,
0:HasComponent,Object,FromCompletedToClosed,,0:TransitionType,
Conformance Units
ISA-95 Job Control Job Order Receiver SubStates


The components of the ObjectType have additional references which are defined in Table 44.

Table 44 - ISA95EndedStateMachineType additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
FromCompletedToClosed,0:FromState,True,Completed
,0:ToState,True,Closed

The component Variables of the ISA95EndedStateMachineType have additional Attributes defined in Table 45.

Table 45 - ISA95EndedStateMachineType Attribute values for child Nodes
BrowsePath,Value Attribute,Description
Completed,,The job order has been completed and is no longer in execution.
"Completed
0:StateNumber",1,
Closed,,The job order has been completed and no further post processing is performed.
"Closed
0:StateNumber",2,
FromCompletedToClosed,,This transition is triggered when the system has finalized post processing of a ended job order.
"FromCompletedToClosed
0:TransitionNumber",1,

6.2.5 ISA95InterruptedStateMachineType

This ObjectType describes a SubStateMachine a job order may use when being interrupted. The ObjectType formally defined in Table 46.

Table 46 - ISA95InterruptedStateMachineType definition
Attribute,Value
BrowseName,ISA95InterruptedStateMachineType
IsAbstract,False
References,Node Class,BrowseName,DataType,TypeDefinition,Other
"Subtype of the 0:FiniteStateMachineType defined in OPC 10000-16, i.e. inheriting the InstanceDeclarations of that Node."
0:HasComponent,Object,Held,,0:StateType,
0:HasComponent,Object,Suspended,,0:StateType,
0:HasComponent,Object,FromHeldToSuspended,,0:TransitionType,
0:HasComponent,Object,FromSuspendedToHeld,,0:TransitionType,
Conformance Units
ISA-95 Job Control Job Order Receiver SubStates


The components of the ObjectType have additional references which are defined in Table 47.

Table 47 - ISA95InterruptedStateMachineType additional References
SourceBrowsePath,Reference Type,Is Forward,TargetBrowsePath
FromHeldToSuspended,0:FromState,True,Held
,0:ToState,True,Suspended
FromSuspendedToHeld,0:FromState,True,Suspended
,0:ToState,True,Held

The component Variables of the ISA95InterruptedStateMachineType have additional Attributes defined in Table 48.

Table 48 - ISA95InterruptedStateMachineType Attribute values for child Nodes
BrowsePath,Value Attribute,Description
Held,,The job order has been temporarily stopped due to a constraint of some form.
"Held
0:StateNumber",1,
Suspended,,The job order has been temporarily stopped due to a deliberate decision within the execution system.
"Suspended
0:StateNumber",2,
FromHeldToSuspended,,"This transition is triggered when the system has switched the job order from internally held to externally suspended, for example by a call of the Pause Method."
"FromHeldToSuspended
0:TransitionNumber",1,
FromSuspendedToHeld,,"This transition is triggered when the system has switched the job order from externally suspended to an internal held, for example by a call of the Resume Method."
"FromSuspendedToHeld
0:TransitionNumber",2,

6.2.6 ISA95JobOrderStatusEventType

The ObjectType defines Events that can be send out every time the state of a job order is changing.


            Table 49 contains the AddressSpace definition of an ISA95JobOrderReceiverObjectType.

Table 49 - ISA95JobOrderStatusEventType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobOrderStatusEventType
IsAbstract,True
References,NodeClass,BrowseName,Data Type,TypeDefinition,Other
Subtype of the 0:BaseEventType defined in OPC 10000-5
0:HasProperty,Variable,JobOrder,ISA95JobOrderDataType,0:PropertyType,M
0:HasProperty,Variable,JobState,ISA95StateDataType[],0:PropertyType,M
0:HasProperty,Variable,JobResponse,ISA95JobResponseDataType,0:PropertyType,M
Conformance Units
ISA-95 Job Control Job Response Provider Job Order Status Events


The JobOrder contains the planned job order received by the system.

The JobState contains the current state of the job order. Clients may filter for Events of specific states, for example only receiving Events of ended job orders. The array shall provide at least one entry representing the top level state and potentially additional entries representing substates. The first entry shall be the top level entry, having the BrowsePath set to null. The order of the substates is not defined.

The JobResponse contains the current job response of the job order. The State in the JobResponse shall be identical to the JobState.

6.2.7 ISA95JobResponseProviderObjectType

6.2.7.1 Overview

The ISA95JobResponseProviderObjectType contains a method to receive unsolicited job response requests as illustrated in Figure 6.

[Figure: Figure 6 - ISA95JobResponseProvider Methods]


              Table 50 is the AddressSpace definition of an ISA95JobResponseProviderObjectType.

Table 50 - ISA95JobResponseProviderObjectType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobResponseProviderObjectType
IsAbstract,False
References,Node Class,BrowseName,Data Type,TypeDefinition,Other
Subtype of the BaseObjectType defined in OPC 10000-5
0:HasComponent,Method,RequestJobResponseByJobOrderID,,See 6.2.7.2,M
0:HasComponent,Method,RequestJobResponseByJobOrderState,,See 6.2.7.3,M
0:HasComponent,Variable,JobOrderResponseList,ISA95JobResponse DataType[],BaseData VariableType,O
0:GeneratesEvent,ObjectType,ISA95JobOrderStatusEventType,,,
Conformance Units
ISA-95 Job Response Provider V2



              
                RequestJobResponseByJobOrderID
              
               - Defines the ISA95JobResponseRequest Method which receives requests for Job Responses by JobOrderID.


              
                RequestJobResponseByJobOrderState
              
               - Defines the ISA95JobResponseRequest Method which receives requests for Job Responses by JobOrderState.

The ISA95JobOrderReceiverObjectType with the StoreAndStart Method may be paired with an ISA95JobResponseProviderObjectType and the RequestJobResponseByJobOrderID Method, to send a Job Order and query for a JobResponse. This transaction is illustrated in Figure 7.


              Objects may generate Events of ISA95JobOrderStatusEventType for every change of the state of a job order managed by the Object. In that case, the JobResponse of the Event shall be identical to the entry in the JobOrderResponseList of the job order and the JobOrder to the counterpart job order receiver Objects JobOrderList.

[Figure: Figure 7 - StoreAndStart and RequestJobResponseByJobOrderID Transaction Example]

The JobOrderResponseList, if provided, shall contain one entry for each job order of the corresponding job order receiver Object provided in the JobOrderList which is not in the states AllowedToStart or NotAllowedToStart. That means, for all job orders that have at least started the execution and are still managed by the job order receiver Object, there shall be an entry. The states of the job orders in both lists (JobOrderList and JobOrderResponseList) shall match for each job order.

When a Job Order gets removed from the JobOrderList, it shall also get removed from the JobOrderResponseList.

6.2.7.2 RequestJobResponseByJobOrderID Method

This Method is used to return Job Responses for unsolicited requests for responses from a job order.

The signature of this Method is specified below. Table 51 and Table 52 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	RequestJobResponseByJobOrderID (
		[in]	0:String				JobOrderID	
	[out]	ISA95JobResponseDataType	JobResponse
	[out]	0:UInt64	   	 		ReturnStatus
	);

Table 51 - RequestJobResponseByJobOrderID Method Arguments
Argument,Description
JobOrderID,"Contains an ID of the job order, as specified by the method caller."
JobResponse,"Contains information about the execution of a job order, such as the current status of the job, actual material consumed, actual material produced, actual equipment used, and job specific data."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 52 - RequestJobResponseByJobOrderID Method AddressSpace Definition
Attribute,Value
BrowseName,RequestJobResponseByJobOrderID
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.7.3 RequestJobResponseByJobOrderState Method

This Method is used to return Job Responses for unsolicited requests for responses from a job order.

The signature of this Method is specified below. Table 53 and Table 54 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	RequestJobResponseByJobOrderState (
		[in] 	ISA95StateDataType[]	 	JobOrderState
	[out]	ISA95JobResponseDataType[]	JobResponses
	[out]	0:UInt64	   	 		ReturnStatus
	);

Table 53 - RequestJobResponseByJobOrderState Method Arguments
Argument,Description
JobOrderState,"Contains a job status of the JobResponse to be returned. The array shall provide at least one entry representing the top level state and potentially additional entries representing substates. The first entry shall be the top level entry, having the BrowsePath set to null. The order of the substates is not defined."
JobResponses,"Contains a list of information about the execution of a job order, such as the current status of the job, actual material consumed, actual material produced, actual equipment used, and job specific data."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 54 - RequestJobResponseByJobOrderState Method AddressSpace Definition
Attribute,Value
BrowseName,RequestJobResponseByJobOrderState
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.2.8 ISA95JobResponseReceiverObjectType

6.2.8.1 Overview

A Job Response Receiver receives unsolicited Job Responses, usually as the result of completion of a job, or at intermediate points within the job as illustrated in Figure 8. 

[Figure: Figure 8 - ISA95JobResponseReceiverObjectType]


              Table 55 is the AddressSpace definition of an ISA95JobResponseReceiverObjectType.

Table 55 - ISA95JobResponseReceiverObjectType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobResponseReceiverObjectType
IsAbstract,False
References,NodeClass,BrowseName,Data Type,TypeDefinition,Other
Subtype of the BaseObjectType defined in OPC 10000-5
0:HasComponent,Method,ReceiveJobResponse,,See 6.2.8.2,M
Conformance Units
ISA-95 Job Response Receiver V2



              ReceiveJobResponse - Defines the ReceiveJobResponse Method which receives unsolicited Job Responses.

The ISA95JobOrderReceiverObjectType with the ReceiveJobOrder method may often be paired with an ISA95JobResponseReceiverObjectType and the ReceiveJobResponse method, to send a Job Order and receive a JobResponse. This transaction is illustrated in Figure 9.

[Figure: Figure 9 - ReceiveJobOrder and ReceiveJobResponse Transaction Example]

6.2.8.2 ReceiveJobResponse Method

The ReceiveJobResponse method is used to receive unsolicited Job Responses.

The signature of this Method is specified below. Table 56 and Table 57 specify the Arguments and AddressSpace representation, respectively.


              Signature
            

	ReceiveJobResponse(
	[in]	ISA95JobResponseDataType		JobResponse
	[out]	0:UInt64			   		ReturnStatus
	);

Table 56 - ReceiveJobResponse Method Arguments
Argument,Description
JobResponse,"Contains information about the execution of a job order, such as actual material consumed, actual material produced, actual equipment used, and job specific data."
ReturnStatus,Returns the status of the method execution.


              B.2 defines common values for ReturnStatus.

Method Result Codes are defined as part of the Call service (see OPC 10000-4, or Annex B Table 94, and Table 95).

Table 57 - ReceiveJobResponse Method AddressSpace Definition
Attribute,Value
BrowseName,ReceiveJobResponse
IsAbstract,True
References,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
0:HasProperty,Variable,0:InputArguments,0:Argument[],0:PropertyType,Mandatory
0:HasProperty,Variable,0:OutputArguments,0:Argument[],0:PropertyType,Mandatory

6.3 DataTypes

6.3.1 ISA95EquipmentDataType

The ISA95EquipmentDataType is a subtype of OPC UA Structure that defines an equipment class or a specific piece of equipment, a quantity and unit of measure, an optional description, and an optional collection of properties.

The structure is defined in Table 58.

Table 58 - ISA95EquipmentDataType Structure
Name,Type,Description,Optional
ISA95EquipmentDataType,Structure,,
ID,0:String,An identification of an EquipmentClass or Equipment.,False
Description,0: LocalizedText[],Additional information and description about the equipment.,True
EquipmentUse,0:String,Information about the expected use of the equipment,True
Quantity,0:DecimalString,The quantity of the equipment.,True
EngineeringUnits,0:EUInformation,The Unit of Measure of the quantity.,True
Properties,ISA95PropertyDataType [],"Any associated properties, or empty if there are no properties defined.",True


            Table 59 is the AddressSpace definition of an ISA95EquipmentDataType.

Table 59 - ISA95EquipmentDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95EquipmentDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.2 ISA95StateDataType

The ISA95JobOrderDataType is a subtype of OPC UA Structure that defines the information needed to schedule and execute a job.

The structure is defined in Table 60.

Table 60 - ISA95StateDataType Structure
Name,Type,Description
ISA95StateDataType,Structure,
BrowsePath,0:RelativePath,The browse path of substates. Shall be null when the top-level state is represented.
StateText,0:LocalizedText,The state represented as human readable text. Shall represent the same text as the CurrentState Variable of a StateMachine would.
StateNumber,0:UInt32,The state represented as number. Shall represent the same number as the Number subvariable of the CurrentState Variable of a StateMachine would.


            Table 61 is the AddressSpace definition of an ISA95StateDataType.

Table 61 - ISA95StateDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95StateDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.3 ISA95JobOrderAndStateDataType

The ISA95JobOrderAndStateDataType is a subtype of OPC UA Structure that defines the information needed to schedule and execute a job, including its state.

The structure is defined in Table 62.

Table 62 - ISA95JobOrderAndStateDataType Structure
Name,Type,Description
ISA95JobOrderAndStateDataType,Structure,
JobOrder,ISA95JobOrderDataType,The job order
State,ISA95StateDataType[],"The State of the job order. The array shall provide at least one entry representing the top level state and potentially additional entries representing substates. The first entry shall be the top level entry, having the BrowsePath set to null. The order of the substates is not defined."


            Table 63 is the AddressSpace definition of an ISA95JobOrderAndStateDataType.

Table 63 - ISA95JobOrderAndStateDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobOrderAndStateDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2

6.3.4 ISA95JobOrderDataType

The ISA95JobOrderDataType is a subtype of OPC UA Structure that defines the information needed to schedule and execute a job.

The structure is defined in Table 64.

Table 64 - ISA95JobOrderDataType Structure
Name,Type,Description,Optional
ISA95JobOrderDataType,Structure,,
JobOrderID,0:String,An identification of the Job Order.,False
Description,0:LocalizedText[],Additional information about the Job Order. The array allows to provide descriptions in different languages.,True
WorkMasterID,ISA95WorkMasterDataType[],"Work Master associated with the job order. If multiple work masters are defined, then the execution system can select the work master based on the availability of resources. If no WorkMaster is defined, then the server may use internal logic or human interactions to select the appropriate WorkMaster.",True
StartTime,0:DateTime,"The proposed start time for the job order, may be empty if not specified.",True
EndTime,0:DateTime,"The proposed end time for the job order, may be empty if not specified.",True
Priority,0:Int16,"The priority of the job order, may be empty if not specified. Higher numbers have higher priority. This type allows the Job Order clients to pick their own ranges, and the Job Order server only has to pick the highest number.",True
JobOrderParameters,ISA95ParameterDataType[],"Key value pairs, not associated with a resource, that are provided as part of the job order, may be empty if not specified.",True
PersonnelRequirements,ISA95PersonnelDataType[],"A specification of any personnel requirements associated with the job order, may be empty if not specified.",True
EquipmentRequirements,ISA95EquipmentDataType[],"A specification of any equipment requirements associated with the job order, may be empty if not specified.",True
PhysicalAssetRequirements,ISA95PhysicalAssetDataType[],"A specification of any physical asset requirements associated with the job order, may be empty if not specified.",True
MaterialRequirements,ISA95MaterialDataType[],"A specification of any material requirements associated with the job order, may be empty if not specified.",True


            Table 65 is the AddressSpace definition of an ISA95JobOrderDataType.

Table 65 - ISA95JobOrderDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobOrderDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2

6.3.5 ISA95JobResponseDataType

The ISA95JobResponseDataType is a subtype of OPC UA Structure that defines the information needed report on the execution of a job order.

The structure is defined in Table 66 .

Table 66 - ISA95JobResponseDataType Structure
Name,Type,Description,Optional
ISA95JobResponseDataType,structure,,
JobResponseID,0:String,A unique identification of the Job Response.,False
Description,0:LocalizedText,Additional information about the Job Response.,True
JobOrderID,0:String,Identification of the job order associated with the job response.,False
StartTime,0:DateTime,The actual start time for the job order.,True
EndTime,0:DateTime,"The actual end time for the job order, may be empty if the job has not yet completed.",True
JobState,ISA95StateDataType[],"The current state of the job. The array shall provide at least one entry representing the top level state and potentially additional entries representing substates. The first entry shall be the top level entry, having the BrowsePath set to null. The order of the substates is not defined.",False
JobResponseData,ISA95ParameterDataType[],"Key value pair with values, not associated with a resource that is provided as part of the job response, may be empty if not specified.",True
PersonnelActuals,ISA95PersonnelDataType[],"A specification of any personnel actuals associated with the job response, may be empty if not specified.",True
EquipmentActuals,ISA95EquipmentDataType[],"A specification of any equipment actuals associated with the job response, may be empty if not specified.",True
PhysicalAssetActuals,ISA95PhysicalAssetDataType[],"A specification of any physical asset actuals associated with the job response, may be empty if not specified.",True
MaterialActuals,ISA95MaterialDataType[],"A specification of any material actuals associated with the job response, may be empty if not specified.",True


            Table 67 is the AddressSpace definition of an ISA95JobResponseDataType.

Table 67 - ISA95JobResponseDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95JobResponseDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.6 ISA95MaterialDataType

The ISA95MaterialDataType is a subtype of OPC UA Structure that defines a material resource, and an optional description, material use, quantity and unit of measure, description, and collection of properties.

The structure is defined in Table 68.

Table 68 - ISA95MaterialDataType Structure
Name,Type,Description,Optional
ISA95MaterialDataType,Structure,,
MaterialClassID,0:String,"An identification of a Material Class, or null if the Material Class is not used to identify the material.  Note: Either a MaterialClassID, MaterialDefinitionID, MaterialLotID, or MaterialSublotID must be defined.",True
MaterialDefinitionID,0:String,"An identification of a Material Definition, or null if the Material Definition is not used to identify the material.",True
MaterialLotID,0:String,"An identification of a Material Lot, or null if the Material Lot is not used to identify the material.",True
MaterialSublotID,0:String,"An identification of a Material Sublot, or null if the Material Sublot is not used to identify the material.",True
Description,0:LocalizedText[],"Additional information and description about the material. The array allows to provide descriptions in different languages when writing. When accessing, the server shall only provide one entry in the array.",True
MaterialUse,0:String,"Information about the expected use of the material. Defined values from ANSI/ISA 95 Part 2 are:                        consumable: resources that are not normally included in bills of material or are not individually accounted for in specific operations requests or are not lot tracked.                        material consumed: raw and intermediate material normally included in bills of material or are individually accounted for in specific operations requests or are material lots tracked.                        material produced: finished goods material normally included in bills of material or are individually accounted for in specific operations requests or are material lots tracked.                        co-product produced: a planned product typically produced in conjunction with a main planned product per the material master. A product that is usually manufactured together or sequentially because of product or process similarities.                        by-product produced: tracked waste, undesirable materials, material of value produced as a residual of or incidental to the production process. The ratio of by-product to primary product is usually predictable. By-products may be recycled, sold as-is, or used for other purposes",True
Quantity,0:DecimalString,The quantity of the material.,True
EngineeringUnits,0:EUInformation,The Unit of Measure of the quantity.,True
Properties,ISA95PropertyDataType[],"Any associated properties of the material, or empty if there are no material properties defined.",True


            Table 69 is the AddressSpace definition of an ISA95MaterialDataType.

Table 69 - ISA95MaterialDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95MaterialDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.7 ISA95PersonnelDataType

The ISA95PersonnelDataType is a subtype of OPC UA Structure that defines a personnel resource and an optional description, personnel use, quantity and unit of measure, description, and collection of properties.

The structure is defined in Table 70.

Table 70 - ISA95PersonnelDataType Structure
Name,Type,Description,Optional
ISA95PersonnelDataType,structure,,
ID,0:String,An identification of a Personnel Class or Person.,False
Description,0:LocalizedText[],"Additional information and description about the resource. The array allows to provide descriptions in different languages when writing. When accessing, the server shall only provide one entry in the array.",True
PersonnelUse,0:String,Information about the expected use of the personnel.,True
Quantity,0:DecimalString,The quantity of the resource.,True
EngineeringUnits,0:EUInformation,The Unit of Measure of the quantity.,True
Properties,ISA95PropertyDataType[],"Any associated properties, or empty if there are no properties defined.",True


            Table 71 is the AddressSpace definition of an ISA95PersonnelDataType.

Table 71 - ISA95PersonnelDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95PersonnelDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.8 ISA95PhysicalAssetDataType

The ISA95PhysicalAssetDataType is a subtype of OPC UA Structure that defines a physical asset resource and an optional description, physical asset use, quantity and unit of measure, description, and collection of properties.

The structure is defined in Table 72.

Table 72 - ISA95PhysicalAssetDataType Structure
Name,Type,Description,Optional
ISA95PhysicalAssetDataType,structure,,
ID,0:String,An identification of a Physical Asset Class or Physical Asset.,False
Description,0:LocalizedText[],"Additional information and description about the physical asset. The array allows to provide descriptions in different languages when writing. When accessing, the server shall only provide one entry in the array.",True
PhysicalAssetUse,0:String,Information about the expected use of the physical asset.,True
Quantity,0:DecimalString,The quantity of the physical asset.,True
EngineeringUnits,0:EUInformation,The Unit of Measure of the quantity.,True
Properties,ISA95PropertyDataType[],"Any associated properties, or empty if there are no physical asset properties defined.",True


            Table 73 is the AddressSpace definition of an ISA95PhysicalAssetDataType.

Table 73 - ISA95PhysicalAssetDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95PhysicalAssetDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.9 ISA95PropertyDataType

The ISA95PropertyDataType is a subtype of OPC UA Structure that defines an ID (which is a unique identifier for a property within the scope of the associated resource), the associated value, (which is the data for the property), and optional description, unit of measure of the value, and subproperties. The structure is defined in Table 74.

Table 74 - ISA95PropertyDataType Structure
Name,Type,Description,Optional
ISA95PropertyDataType,structure,,
ID,0:String,Unique identifier for a property within the scope of the associated resource,False
Value,0:BaseDataType,Value for the property,False
Description,0:LocalizedText[],"An optional description of the property. The array allows to provide descriptions in different languages when writing. When accessing, the server shall only provide one entry in the array.",True
EngineeringUnits,0:EUInformation,The Unit of Measure of the value,True
Subproperties,ISA95PropertyDataType[],Sub properties of the property,True


            Table 75 is the AddressSpace definition of an ISA95PropertyDataType.

Table 75 - ISA95PropertyDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95PropertyDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.10 ISA95ParameterDataType

The ISA95ParameterDataType is a subtype of OPC UA Structure that defines an ID (which is a unique identifier for a parameter), the associated value (which is the data for the parameter), and optional description, unit of measure of the value, and subproperties. The structure is defined in Table 74.

Table 76 - ISA95ParameterDataType Structure
Name,Type,Description,Optional
ISA95ParameterDataType,Structure,,
ID,0:String,A unique identifier for a parameter,False
Value,0:BaseDataType,Value of the parameter.,False
Description,0:LocalizedText[],"An optional description of the parameter. The array allows to provide descriptions in different languages when writing. When accessing, the server shall only provide one entry in the array.",True
EngineeringUnits,0:EUInformation,The Unit of Measure of the value,True
Subparameters,ISA95ParameterDataType[],Sub parameters of the parameter,True


            Table 77 is the AddressSpace definition of an ISA95PropertyDataType.

Table 77 - ISA95ParameterDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95ParameterDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2
ISA-95 Job Response Provider V2
ISA-95 Job Response Receiver V2

6.3.11 ISA95WorkMasterDataType

The ISA95WorkMasterDataType is a subtype of OPC UA Structure that defines a Work Master ID and optional description and parameters for the Work Master.

The structure is defined in Table 78.

Table 78 - ISA95WorkMasterDataType Structure
Name,Type,Description,Optional
ISA95WorkMasterDataType,structure,,
ID,0:String,An identification of the Work Master.,False
Description,0:LocalizedText,Additional information and description about the Work Master.,True
Parameters,ISA95ParameterDataType[],Defined parameters for the Work Master.,True


            Table 79 is the AddressSpace definition of an ISA95WorkMasterDataType.

Table 79 - ISA95WorkMasterDataType AddressSpace Definition
Attribute,Value
BrowseName,ISA95WorkMasterDataType
IsAbstract,False
Reference,NodeClass,BrowseName,DataType,TypeDefinition,ModellingRule
Subtype of the Structure defined in OPC 10000-5
Conformance Units
ISA-95 Job Order Receiver V2

7 Profiles and Conformance Units


        Profiles and ConformanceUnits break functionality into testable groups. A ConformanceUnit describes a testable unit. A single ConformanceUnit is tested as a unit so all items covered by it must be supported or the ConformanceUnit will fail. ConformanceUnits can be included in multiple Profiles, so they are declared in their own table.

7.1 Conformance Units

This chapter defines the corresponding Conformance Units for this document.


          Table 80 defines the Server and Client ConformanceUnits. 

Table 80 - Conformance Units for ISA-95 Job Control
Category,Title,Description
Server,ISA-95 Job Control StoreAndStart,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the StoreAndStart Method.
Server,ISA-95 Job Control Store and Start and RevokeStart,"Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Store, Start and RevokeStart Methods."
Server,ISA-95 Job Control Starting,Server supports at least one of the following conformance units: ISA-95 Job Control StoreAndStart or ISA-95 Job Control Store and Start and RevokeStart
Server,ISA-95 Job Control Update,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Update Method.
Server,ISA-95 Job Control Pause and Resume,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Pause and Resume Methods.
Server,ISA-95 Job Control Stop,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Stop Method.
Server,ISA-95 Job Control Abort,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Abort Method.
Server,ISA-95 Job Control Clear,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Clear Method.
Server,ISA-95 Job Control Cancel,Server supports at least one instance of the ISA95JobOrderReceiverObjectType implementing the Cancel Method.
Server,ISA-95 Job Control Job Order Receiver SubStates,"The server supports the ISA95JobOrderReceiverSubStatesType, the ISA95PrepareStateMachineType, the ISA95EndedStateMachineType and the ISA95InterruptedStateMachineType."
Server,ISA-95 Job Control Job Response Provider JobOrderResponseList,The server supports at least one instance of ISA95JobResponseProviderObjectType supporting the JobOrderResponseList.
Server,ISA-95 Job Control Job Response Provider Job Order Status Events,The server supports at least one instance of ISA95JobResponseProviderObjectType and the ISA95JobOrderStatusEventType. Each instance of ISA95JobResponseProviderObjectType shall generate the Events on status changes.
Client,ISA-95 Job Control StoreAndStart Client,The client makes use of the StoreAndStart method.
Client,ISA-95 Job Control Store and Start and RevokeStart Client,The client makes use of the Store and Start and RevokeStart methods.
Client,ISA-95 Job Control Update Client,The client makes use of the Update method.
Client,ISA-95 Job Control Pause and Resume Client,The client makes use of the Store and Pause and Resume methods.
Client,ISA-95 Job Control Stop Client,The client makes use of the Stop method.
Client,ISA-95 Job Control Abort Client,The client makes use of the Abort method.
Client,ISA-95 Job Control Clear Client,The client makes use of the Clear method.
Client,ISA-95 Job Control Cancel Client,The client makes use of the Cancel method.
Client,ISA-95 Job Control Job Order Receiver SubStates Client,"The client makes use of the ISA95JobOrderReceiverSubStatesType, the ISA95PrepareStateMachineType, the ISA95EndedStateMachineType and the ISA95InterruptedStateMachineType."
Client,ISA-95 Job Control Job Response Provider JobOrderResponseList Client,The client makes use of the JobOrderResponseList.
Client,ISA-95 Job Control Job Response Provider Job Order Status Events Client,The client makes use of the job order status events.
Server,ISA-95 Job Order Receiver V2,The server supports the ISA95JobOrderReceiverObjectType.
Server,ISA-95 Job Response Provider V2,The server supports the ISA95JobResponseProviderObjectType.
Server,ISA-95 Job Response Receiver V2,The server supports the ISA95JobResponseReceiverObjectType.
Client,ISA-95 Job Order Receiver Client V2,The client makes use of the ReceiveJobOrder method.
Client,ISA-95 Job Response Provider Client V2,The client makes use of the RequestJobResponseByJobOrderID or RequestJobResonseByJobOrderState method.
Client,ISA-95 Job Response Receiver Client V2,The client makes use of the ReceiveJobResponse method.

7.1.1 Profile list


            Table 81 lists all Profiles defined in this document and defines their URIs.

Table 81 - Profile URIs for ISA-95 Job Control
Profile Name,URI
ISA-95 Job Order Receiver Client V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Client/JobOrderReceiverV2
ISA-95 Job Order Receiver Server V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Server/JobOrderReceiverV2
ISA-95 Job Order Status Events Server Facet,http://opcfoundation.org/UA-Profile/ISA-95/Server/JobOrderStatusEvents
ISA-95 Job Order Status Events Client Facet,http://opcfoundation.org/UA-Profile/ISA-95/Client/JobOrderStatusEvents
ISA-95 Job Response Provider Client V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Client/JobResponseProviderV2
ISA-95 Job Response Provider Server V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Server/JobResponseProviderV2
ISA-95 Job Response Receiver Client V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Client/JobResponseReceiverV2
ISA-95 Job Response Receiver Server V2 Facet,http://opcfoundation.org/UA-Profile/ISA-95/Server/JobResponseReceiverV2


            Table 82 lists the general functionality of client and server profiles that support the ISA-95 OPC UA interface.

Table 82 - Profile Overview
Profile,Example,"Methods, Variables and Events"
Job Order Receiver Client V2 Facet,Sends unsolicited Job Orders to a Job Order Receiver Server,"Uses Store, StoreAndStart, Start, Store, RevokeStart, Pause, Resume, Stop, Abort, Clear, Cancel  Uses JobOrderList"
Job Order Receiver Server V2 Facet,"Receives unsolicited Job Orders and associated commands, and exposes allowable work masters, material, equipment, physical asset, and personnel ID that may be used in a Job Order.","Store, StoreAndStart, Start, Store, RevokeStart, Pause, Resume, Stop, Abort, Clear, Cancel JobOrderList WorkMaster MaterialClassID MaterialDefinitionID EquipmentID PhysicalAssetID PersonnelID"
Job Response Provider Client V2 Facet,Sends unsolicited request for Job Responses to a Job Response Provider Server,Uses RequestJobResponseByJobOrderID or RequestJobResonseByJobOrderState Uses JobOrderResponseList
Job Order Status Events Server Facet,Sends unsolicited status changes of a Job Order as Events.,JobOrderStatusEvents
Job Order Status Events Client Facet,Receives unsolicited changes of job orders as events.,Uses JobOrderStatusEvents
Job Response Provider Server V2 Facet,Receives unsolicited Job Response Requests for a specific Job Order,RequestJobResponseByJobOrderID RequestJobResonseByJobOrderState JobOrderResponseList
Job Response Receiver Client V2 Facet,Sends unsolicited Job Responses to a Job Response Receiver Server,Uses ReceiveJobResponse
Job Response Receiver Server V2 Facet,Receives unsolicited Job Responses for a Job Order,ReceiveJobResponse

See Figure 7 and Figure 9 as examples of the use of the specified profiles to provide control of job orders and job reports. 

7.2 Profiles

7.2.1 Server Facets

7.2.1.1 Overview

The following sections specify the Facets available for Servers that implement the ISA-95 Job Control companion specification. Each section defines and describes a Facet or Profile.

7.2.1.2 ISA-95 Job Order Receiver Server V2 Facet


              Table 83 defines a Facet that describes a Server that supports receiving job orders. 

Table 83 - ISA-95 Job Order Receiver Server V2 Facet
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Control Starting,M
ISA-95 Job Control,ISA-95 Job Order Receiver V2,M
ISA-95 Job Control,ISA-95 Job Control StoreAndStart,O
ISA-95 Job Control,ISA-95 Job Control Store and Start and RevokeStart,O
ISA-95 Job Control,ISA-95 Job Control Update,O
ISA-95 Job Control,ISA-95 Job Control Pause and Resume,O
ISA-95 Job Control,ISA-95 Job Control Stop,O
ISA-95 Job Control,ISA-95 Job Control Abort,O
ISA-95 Job Control,ISA-95 Job Control Clear,M
ISA-95 Job Control,ISA-95 Job Control Cancel,M
ISA-95 Job Control,ISA-95 Job Control Job Order Receiver SubStates,O

7.2.1.3 ISA-95 Job Order Status Events Server Facet


              Table 84 defines a Facet that describes a Server that provides Job Order Status Events.

Table 84 - ISA-95 Job Order Status Events Server Facet
Group,Conformance Unit / Profile Title,M / O
Profile,0:Standard Event Subscription Server Facet,
ISA-95 Job Control,ISA-95 Job Control Job Response Provider Job Order Status Events,M

7.2.1.4 ISA-95 Job Response Provider Server V2 Facet


              Table 85 defines a Facet that describes a Server that has the RequestJobResponseByJobOrderID and RequestJobResonseByJobOrderState Method.

Table 85 - ISA-95 Job Response Provider Server V2 Facet
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Response Provider V2,M
ISA-95 Job Control,ISA-95 Job Control Job Response Provider JobOrderResponseList,O

7.2.1.5 ISA-95 Job Response Receiver Server V2 Facet


              Table 86 defines a Facet that describes a Server that has the ReceiveJobResponse Method.

Table 86 - ISA-95 Job Response Receiver Server V2 Facet
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Response Receiver V2,M

7.2.2 Client Facets

7.2.2.1 Overview

The following tables specify the Facets available for Clients that implement the ISA-95 Job Control companion specification.

7.2.2.2 ISA-95 Job Order Receiver Client V2 Facet


              Table 87 defines a Facet that describes a Client that uses the job order receiver Object. 

Table 87 - ISA-95 Job Order Receiver Client Facet Definition
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Order Receiver Client V2,M
ISA-95 Job Control,ISA-95 Job Control StoreAndStart Client,M
ISA-95 Job Control,ISA-95 Job Control Store and Start and RevokeStart Client,M
ISA-95 Job Control,ISA-95 Job Control Update Client,O
ISA-95 Job Control,ISA-95 Job Control Pause and Resume Client,O
ISA-95 Job Control,ISA-95 Job Control Stop Client,O
ISA-95 Job Control,ISA-95 Job Control Abort Client,O
ISA-95 Job Control,ISA-95 Job Control Clear Client,M
ISA-95 Job Control,ISA-95 Job Control Cancel Client,M
ISA-95 Job Control,ISA-95 Job Control Job Order Receiver SubStates Client,O

7.2.2.3 ISA-95 Job Order Status Events Client Facet


              Table 88 defines a Facet that describes a Client receiving Job Order Status Events. 

Table 88 - ISA-95 Job Order Status Events Client Facet Definition
Group,Conformance Unit / Profile Title,M / O
Profile,0:Event Subscriber Client Facet,
ISA-95 Job Control,ISA-95 Job Control Job Response Provider Job Order Status Events Client,M

7.2.2.4 ISA-95 Job Response Provider Client V2 Facet


              Table 89 defines a Facet that describes a Client that uses the RequestJobResponseByJobOrderID or RequestJobResonseByJobOrderState Method. 

Table 89 - ISA-95 Job Response Provider Client V2 Facet Definition
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Response Provider Client V2,M
ISA-95 Job Control,ISA-95 Job Control Job Response Provider JobOrderResponseList Client,O

7.2.2.5 ISA-95 Job Response Receiver Client V2 Facet


              Table 90 defines a Facet that describes a Client that uses the ReceiveJobResponse Method. 

Table 90 - ISA-95 Job Response Receiver Client V2 FacetDefinition
Group,Conformance Unit / Profile Title,M / O
ISA-95 Job Control,ISA-95 Job Response Receiver Client V2,M

8 Namespaces

8.1 Namespace Metadata


          Table 91 defines the namespace metadata for this specification. The Object is used to provide version information for the namespace and an indication about static Nodes. Static Nodes are identical for all Attributes in all Servers, including the Value Attribute. See OPC 10000-5 for more details.

The information is provided as Object of type NamespaceMetadataType. This Object is a component of the Namespaces Object that is part of the Server Object. The NamespaceMetadataType ObjectType and its Properties are defined in OPC 10000-5.

The version information is also provided as part of the ModelTableEntry in the UANodeSet XML file. The UANodeSet XML schema is defined in OPC 10000-6.

Table 91 - NamespaceMetadata Object for this Specification
Attribute,Value
BrowseName,http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/
Property,DataType,Value
NamespaceUri,String,http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/
NamespaceVersion,String,2.0.0
NamespacePublicationDate,DateTime,2024-01-31
IsNamespaceSubset,Boolean,False
StaticNodeIdTypes,IdType [],0
StaticNumericNodeIdRange,NumericRange [],1:2147483647
StaticStringNodeIdPattern,String,0

8.2 Handling of OPC UA Namespaces

Namespaces are used by OPC UA to create unique identifiers across different naming authorities. The Attributes NodeId and BrowseName are identifiers. A Node in the UA AddressSpace is unambiguously identified using a NodeId. Unlike NodeIds, the BrowseName cannot be used to unambiguously identify a Node. Different Nodes may have the same BrowseName. They are used to build a browse path between two Nodes or to define a standard Property.


          Servers may often choose to use the same namespace for the NodeId and the BrowseName. However, if they want to provide a standard Property, its BrowseName shall have the namespace of the standards body although the namespace of the NodeId reflects something else, for example the EngineeringUnits Property. All NodeIds of Nodes not defined in this document shall not use the standard namespaces.


          Table 92 provides a list of mandatory and optional namespaces used in an ISA 95 Job Control OPC UA Server.

Table 92 - Namespaces used in an ISA 95 Job Control Server
NamespaceURI,Description,Use
http://opcfoundation.org/UA/,Namespace for NodeIds and BrowseNames defined in the OPC UA specification. This namespace shall have namespace index 0.,Mandatory
Local Server URI,Namespace for nodes defined in the local server. This namespace shall have namespace index 1.,Mandatory
http://opcfoundation.org/UA/ISA95JobControl/,Namespace for NodeIds and BrowseNames defined in this document. The namespace index is Server specific.,Mandatory
Vendor specific types,A Server may provide vendor-specific types like types derived from ObjectTypes defined in this document in a vendor-specific namespace.,Optional
Vendor specific instances,A Server provides vendor-specific instances of the standard types or vendor-specific instances of vendor-specific types in a vendor-specific namespace. It is recommended to separate vendor specific types and vendor specific instances into two or more namespaces.,Mandatory


          Table 93 provides a list of namespaces and their indices used for BrowseNames in this document. The default namespace of this document is not listed since all BrowseNames without prefix use this default namespace.

Table 93 - Namespaces used in this document
NamespaceURI,Namespace Index,Example
http://opcfoundation.org/UA/,0,0:EngineeringUnits

Annex A (normative):ISA95 Job Control Namespace and mappings

A.1 Namespace and identifiers for ISA95 Job Control Information Model

The ISA-95 Job Control Information Model is identified by the following URI:


          http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/
        

Documentation for the NamespaceUri can be found here (https://reference.opcfoundation.org/nodesets?u=http://opcfoundation.org/UA/ISA95_JOBCONTROL_V2).

The NodeSet associated with this version of specification can be found here:


          https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&v=2.0.0&i=1 (https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&v=2.0.0&i=1) 

The NodeSet associated with the latest version of the specification can be found here:


          https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&i=1 (https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&i=1) 

Supplementary files for the ISA95 Job Control Information Model can be found here:


          https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&v=2.0.0&i=2 (https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&v=2.0.0&i=2) 

The files associated with the latest version of the specification can be found here:


          https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&i=2 (https://reference.opcfoundation.org/nodesets/?u=http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/&i=2) 

Annex B OPC UA Method result Codes

B.1 Method Result Codes (Informative)

The OPC UA Method Result codes, from OPC 10000-4, are copied in Table 94. 

Table 94 - OPC UA Method Result Codes
Result Code,Description
Bad_MethodInvalid,See OPC 10000-4 for the description of this result code. (The method id does not refer to a method for the specified object.)
Bad_NotImplemented,See OPC 10000-4 for the description of this result code. (Requested operation is not implemented.)
Bad_NodeIdUnknown,See OPC 10000-4 for the description of this result code. (Used to indicate that the specified object is not valid)
Bad_ArgumentsMissing,See OPC 10000-4 for the description of this result code (The client did not specify all of the input arguments for the method.)
Bad_TooManyArguments,See OPC 10000-4 for the description of this result code (The client specified more input arguments than defined for the method.)
Bad_InvalidArgument,See OPC 10000-4 for the description of this result code. (Used to indicate in the operation level results that one or more of the input arguments are invalid. The inputArgumentResults contain the specific status code for each invalid argument.)
Bad_TypeMismatch,See OPC 10000-4 for the description of this result code. (Used to indicate that an input argument does not have the correct data type.)
Bad_OutOfRange,See OPC 10000-4 for the description of this result code. (Used to indicate that an input argument is outside the acceptable range.)
Bad_Timeout,See OPC 10000-4 for the description of this result code. (The operation timed out. - the server did not respond to the command)
Bad_InvalidState,"See OPC 10000-4 for the description of this result code. (The operation cannot be completed because the object is closed, uninitialized or in some other invalid state.)"

B.2 Job Order Method Return Status Codes

The job order methods' return status codes are defined as a bit map in a UInt64 variable, allowing for multiple codes to be defined at the same time. The codes and bitmap positions are defined in Table 95. In the OPC format, the bit positions start at bit 0 for the least significant digit.

Note: In case the ReturnStatus should be provided, the Method call cannot return a BAD StatusCode (then no return arguments are provided) but either the GOOD StatusCode, or an UNCERTAIN StatusCode (when the Method call was not successful). 

Table 95 - ISA-95 Methods Return Status Codes
Bit Position,Description,Notes
0,No Error,If bit 0 set (UInt64 value = 1) then there are no errors. This is returned on all successful method calls.
1,Unknown Job Order ID,The Job Order ID is unknown by the Information Receiver/Provider
3,Invalid Job Order Status,The Job Order status is unknown.
4,Unable to accept Job Order,The Job Order cannot be accepted
5-31,Reserved,
32,Invalid request,The request is invalid due to an unspecified reason.
33-63,Implementation-specific,These values are reserved for use in specific implementations and should be defined in the implementation specification.

Annex C (Informative):Example Job Orders

C.1 Simple Job Order

The following example, in JSON format, defines a simple Job Order that defines a packaging order that contains three levels of packaging, and quantities for each level. The example uses project specific properties.

	
{
  "Job Order": {
    "ID": "4568724",
    "Description": "A simple job order which uses pre-defined material master data",
    "JobOrderParameters": [
      {
        "ID": "Item Expiration Date",
        "Value": "2022-12-31T23:59:59+01:00"
      },
      {
        "ID": "Printed Item Expiration Date",
        "Value": "2022-12-31"
      },
      {
        "ID": "ERP Order Number",
        "Value": "TestOrderNo2"
      },
      {
        "ID": "Param1",
        "Value": "XXX"
      },
      {
        "ID": "Event Context":'
  	  "Subparameters":[
  	   {
          "ID": "OrderID", "EngineeringUnits": "L3OrderId", "value": "IAmJustAnOrderID"
          }
 	 ]
      }
    ],
    "MaterialRequirement": {
      "MaterialDefinitionID": "A548646-5",
      "Quantity": 500000
    }
  }
}

C.2 Job Order with Packaging Master Data

The following example, in JSON format, defines a more complex Job Order that defines a packaging order that contains three levels of packaging, quantities for each level, and details for each packaging level. The example uses project specific properties. 

	
{
  "Job Order": {
    "ID": "81e54f03-9e4e-48c9-97e6-0554f3f6a4a0",
    "Description": "A test job order with all packaging/material master data defined",
    "StartTime": "2020-06-12T12:00:00+01:00",
    "Equipment Requirement": {
      "ID": "LineController#2"
    },
    "JobOrderParameters": [
      {
        "ID": "Item Expiration Date",
        "Value": "2022-12-31T23:59:59+01:00"
      },
      {
        "ID": "Printed Item Expiration Date",
        "Value": "2022-12-31"
      },
      {
        "ID": "ERP Order Number",
        "Value": "TestOrderNo1"
      },
      {
        "Event Context": {
          "EngineeingUnits": "L3OrderId",
          "value": "IAmJustAnOrderID"
        }
      }
    ],
    "Material Requirement": {
      "MaterialDefinitionID": "A548646-5",
      "MaterialLotID": "TestBatchNo",
      "MaterielUse": "material produced",
      "Quantity": "500000",
      "Material Requirement Property": [
        {
          "ID": "Product Name",
          "Value": "Test Material"
        },
        {
          "ID": "Param1",
          "Value": "XXX"
        },
        {
          "ID": "Param2",
          "Value": "XXX"
        },
        {
          "ID": "Product Packaging Code",
          "Value": "0123456712345x",
          "Material Requirement Property": [
            {
              "ID": "Product Packaging Code Type",
              "Value": "GTIN"
            },
            {
              "ID": "Package Type Code",
              "Value": "FOB"
            },
            {
              "ID": "Level Is Serialized",
              "Value": "true"
            },
            {
              "ID": "Has Parent Level",
              "Value": "true"
            },
            {
              "ID": "Has Pre-Printed Serial Numbers",
              "Value": "false"
            },
            {
              "ID": "Is Definition For Partial",
              "Value": "false"
            },
            {
              "ID": "Pool Selection Criteria",
              "Value": "Box#TestBatch#54841",
              "Material Requirement Property": {
                "ID": "Pool Selection Criteria Type",
                "Value": "PoolID"
              }
            }
          ]
        },
        {
          "ID": "Product Packaging Code",
          "Value": "",
          "Material Requirement Property": [
            {
              "ID": "Child Package Type Code",
              "Value": "FOB"
            },
            {
              "ID": "Package Type Code",
              "Value": "BD"
            },
            {
              "ID": "Immediate Children Items Quantity",
              "Value": "5"
            },
            {
              "ID": "Level Is Serialized",
              "Value": "false"
            },
            {
              "ID": "Has Parent Level",
              "Value": "true"
            }
          ]
        },
        {
          "ID": "Product Packaging Code",
          "Value": "3123456712345x",
          "Material Requirement Property": [
            {
              "ID": "Product Packaging Code Type",
              "Value": "GTIN"
            },
            {
              "ID": "Child Package Type Code",
              "Value": "BD"
            },
            {
              "ID": "Package Type Code",
              "Value": "CS"
            },
            {
              "ID": "Immediate Children Items Quantity",
              "Value": "4"
            },
            {
              "ID": "Level Is Serialized",
              "Value": "true"
            },
            {
              "ID": "Has Parent Level",
              "Value": "true"
            },
            {
              "ID": "Has Pre-Printed Serial Numbers",
              "Value": "false"
            },
            {
              "ID": "Is Definition For Partial",
              "Value": "false"
            },
            {
              "ID": "Pool Selection Criteria",
              "Value": "Case#TestBatch#5484#Full",
              "Material Requirement Property": {
                "ID": "Pool Selection Criteria Type",
                "Value": "PoolID"
              }
            }
          ]
        },
        {
          "ID": "Product Packaging Code",
          "Value": "1234567",
          "Material Requirement Property": [
            {
              "ID": "Product Packaging Code Type",
              "Value": "SSCCGCP",
              "Material Requirement Property": {
                "ID": "Product Packaging Code",
                "Value": "5",
                "Material Requirement Property": {
                  "ID": "Product Packaging Code Type",
                  "Value": "SSCCExtension"
                }
              }
            },
            {
              "ID": "Child Package Type Code",
              "Value": "BD"
            },
            {
              "ID": "Package Type Code",
              "Value": "CS"
            },
            {
              "ID": "Immediate Children Items Quantity",
              "Value": "4"
            },
            {
              "ID": "Level Is Serialized",
              "Value": "true"
            },
            {
              "ID": "Has Parent Level",
              "Value": "true"
            },
            {
              "ID": "Has Pre-Printed Serial Numbers",
              "Value": "false"
            },
            {
              "ID": "Is Definition For Partial",
              "Value": "true"
            },
            {
              "ID": "Pool Selection Criteria",
              "Value": "Case#TestBatch#5484#Partial",
              "Material Requirement Property": {
                "ID": "Pool Selection Criteria Type",
                "Value": "PoolID"
              }
            }
          ]
        },
        {
          "ID": "Product Packaging Code",
          "Value": "1234567",
          "Material Requirement Property": [
            {
              "ID": "Product Packaging Code Type",
              "Value": "SSCCGCP",
              "Material Requirement Property": {
                "ID": "Product Packaging Code",
                "Value": "7",
                "Material Requirement Property": {
                  "ID": "Product Packaging Code Type",
                  "Value": "SSCCExtension"
                }
              }
            },
            {
              "ID": "Planned Quantity",
              "Value": "782"
            },
            {
              "ID": "Child Package Type Code",
              "Value": "CS"
            },
            {
              "ID": "Package Type Code",
              "Value": "PX"
            },
            {
              "ID": "Immediate Children Items Quantity",
              "Value": "32"
            },
            {
              "ID": "Level Is Serialized",
              "Value": "true"
            },
            {
              "ID": "Has Parent Level",
              "Value": "false"
            },
            {
              "ID": "Has Pre-Printed Serial Numbers",
              "Value": "false"
            },
            {
              "ID": "Is Definition For Partial",
              "Value": "false"
            },
            {
              "ID": "Pool Selection Criteria",
              "Value": "Pallet#TestBatch#5484#Partial",
              "Material Requirement Property": {
                "ID": "Pool Selection Criteria Type",
                "Value": "PoolID"
              }
            }
          ]
        }
      ]
    }
  }
}    

Bibliography

[[1]] OPC 10000-2, OPC Unified Architecture - Part 2: Security Model

