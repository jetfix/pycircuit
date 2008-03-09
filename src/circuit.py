import unittest
import numpy
from numpy import array, delete, linalg, size, zeros, concatenate, pi, dot, exp
import pylab
import sympy

class Node(object):
    """A node is a region in an electric circuit where the voltage is the same.
    
    A node can have a name
    """
    def __init__(self, name=None):
        self.name = name

    def __repr__(self):
        return self.__class__.__name__ + '(\'' + self.name + '\')'

class Branch(object):
    """A branch connects two nodes.
    
    A branch is used in modified nodal analysis to describe components that defines a voltage between
    two nodes as a function of current flowing between these nodes. Examples are voltage sources and inductors.
    Positive current through a branch is defined as a current flowing from plus to minus.a
    
    """
    def __init__(self, plus, minus, name=None):
        """Initiate a branch

        Arguments:
        plus -- Node object connected to the postive terminal of the branch
        minus -- Node object connected to the negative terminal of the branch

        Keyword arguments:
        name -- branch name

        """

        self.plus = plus
        self.minus = minus
        self.name = name

    def __repr__(self):
        return 'Branch('+str(self.plus)+','+str(self.minus)+')'

### Default reference node
gnd = Node("gnd")

class Circuit(object):
    """The circuit class describes a full circuit, subcircuit or a single component. 

    It contains a list of nodes,terminals and parameters.
    The terminals connect nodes inside the circuit to the nodes outside the circuit. When the circuit is
    instanciated, the outside nodes are passed to the object via the terminals.
       
    Attributes:
    nodes      -- A list that contains Node objects. If the circuit does not contain any internal nodes
                  the length is the same as the number of terminals.
    branches   -- A list of Branch objects. The solver will solve for the currents through the branches.
    terminals  -- A list that contains terminal names
    parameters -- A dictionary of parameter values keyed by the parameter name
    nodenames  -- A dictionary that maps a local node name to the node object in nodes. If the node is
                  connnected to superior hierarchy levels through a terminal the terminal name must
                  be the same as the local node name

    """
    terminals = []
    def __init__(self, **kvargs):
        self.nodes = []
        self.nodenames = {}
        self.branches = []
        self.parameters = {}
        self.x = {}

        for terminal in self.terminals:
            self.addNode(terminal)

        self.connectTerminals(**kvargs)

        
    def addNode(self, name=None):
        """Create an internal node in the circuit and return the new node

        >>> c = Circuit()
        >>> n1 = c.addNode("n1")
        >>> c.nodes
        [Node('n1')]
        >>> 'n1' in c.nodenames
        True
        
        """
        newnode = Node(name)
        self.nodes.append(newnode)
        if name != None:
            self.nodenames[name] = newnode
        return newnode

    def getNodeIndex(self, node):
        """Get row in the x vector of a node"""
        return self.nodes.index(node)

    def getBranchIndex(self, branch):
        return len(self.nodes) + self.branches.index(branch)

    def getNode(self, name):
        """Find a node by name.
        
        >>> c = Circuit()
        >>> n1 = c.addNode("n1")
        >>> c.getNode('n1')
        Node('n1')
        
        """
        return self.nodenames[name]

    def getNodeName(self, node):
        """Find the name of a node
        
        >>> c = Circuit()
        >>> n1 = c.addNode("n1")
        >>> c.getNodeName(n1)
        'n1'

        """
        
        for k, v in self.nodenames.items():
            if v == node:
                return k
        
    def connectTerminals(self, **kvargs):
        """Connect nodes to terminals by using keyword arguments

        """
        for terminal, node in kvargs.items():
            if not terminal in self.terminals:
                raise ValueError('terminal '+str(terminal)+' is not defined')
            if node != None:
                self.nodes.remove(self.nodenames[terminal])
                if not node in self.nodes:
                    self.nodes.append(node)
                self.nodenames[terminal] = node

    def n(self):
        """Return size of x vector"""
        return len(self.nodes) + len(self.branches)

    def G(self, x):
        """Calculate the G ((trans)conductance) matrix of the circuit given the x-vector"""
        return zeros((self.n(), self.n()), dtype=object)

    def C(self, x):
        """Calculate the C (transcapacitance) matrix of the circuit given the x-vector"""
        return zeros((self.n(), self.n()), dtype=object)

    def U(self, t=0.0):
        """Calculate the U column-vector the circuit at time t for a given x-vector.

        """
        return zeros((self.n(), 1), dtype=object)

    def i(self, x):
        """Calculate the i vector as a function of the x-vector

        For linear circuits i(x(t)) = G*x
        """
        return dot(self.G(x), x)

    def CY(self, x, kT):
        """Calculate the noise sources correlation matrix

        @param x:  the state vector
        @type  x:  numpy array
        @param kT: M{kboltzman*T} where T is the temperature in Kelvin
        @type  kT: number        
        """
        return zeros((self.n(), 1), dtype=object)

    def nameStateVector(self, x, analysis=''):
        """Map state variables with names and return the state variables in a dictionary keyed by the names

        >>> c = SubCircuit()
        >>> n1=c.addNode('net1')
        >>> c['is'] = IS(gnd, n1, i=1e-3)
        >>> c['R'] = R(n1, gnd, r=1e3)
        >>> c.nameStateVector(array([[1.0]]))
        {'net1': 1.0}

        >>> 

        """
        result = {}
        for xvalue, node in zip(x[:len(self.nodes)][0], self.nodes):
            result[self.getNodeName(node)] = xvalue

        for i, xvalue, branch in enumerate(zip(x[len(self.nodes):], self.branches)):
            result['i' + analysis + str(i) + ')'] = xvalue            

        return result

        
class SubCircuit(Circuit):
    """
    SubCircuit is container for circuits.
    Attributes:
      elements          dictionary of Circuit objects keyed by its instance name
      elementnodemap    list of translations between node indices of the elements to the
                        node index in the SubCircuit object.
      elementbranchmap  list of translations between branch indices of the elements to the
                        branch index in the SubCircuit object.
    """
    def __init__(self, **kvargs):
        Circuit.__init__(self, **kvargs)
        self.elements = {}
        self.elementnodemap = []
        self.elementbranchmap = []
        
    def __setitem__(self, instancename, element):
        """Adds an instance to the circuit"""
        self.elements[instancename] = element
        
        # Add nodes and branches from new element
        for node in element.nodes:
            if not node in self.nodes:
                self.nodes.append(node)
        self.branches.extend(element.branches)

        self.updateNodeMap()

    def __getitem__(self, instancename):
        """Get instance"""
        return self.elements[instancename]

    def getNode(self, name):
        """Find a node by name.

        The name can be a hierachical name and the notation is 'I1.I2.net1' for
        a net net1 in instance I2 of instance I1
        
        >>> c = Circuit()
        >>> n1 = c.addNode("n1")
        >>> c.getNode('n1')
        Node('n1')

        >>> c1 = SubCircuit()
        >>> c2 = SubCircuit()
        >>> c1['I1'] = c2
        >>> n1 = c2.addNode("net1")
        >>> c1.getNode('I1.net1')
        Node('net1')
        
        """
        hierlevels = [part for part in name.split('.')]
            
        if len(hierlevels)==1:
            return self.nodenames[hierlevels[0]]
        else:
            return self.elements[hierlevels[0]].getNode('.'.join(hierlevels[1:]))

    def getNodeName(self, node):
        """Find the name of a node
        
        >>> c1 = SubCircuit()
        >>> c2 = SubCircuit()
        >>> c1['I1'] = c2
        >>> n1 = c2.addNode("net1")
        >>> c1.getNodeName(n1)
        'net1'

        """

        ## Use name of node object if present
        if node.name != None:
            return node.name
        
        ## First search among the local nodes
        name = Circuit.getNodeName(self, node)
        if name != None:
            return name
        
        ## Then search in the circuit elements
        for instname, element in self.elements.items():
            name =  element.getNodeName(node)
            if name != None:
                return instname + '.' + name
        
    def updateNodeMap(self):
        """Update the elementnodemap attribute"""

        self.elementnodemap = {}
        for instance, element in self.elements.items():
            self.elementnodemap[instance] = [self.nodes.index(node) for node in element.nodes] + \
                                            [self.branches.index(branch)+len(self.nodes) for branch in element.branches]

    def G(self, x):
        return self._add_element_submatrices('G', x, ())

    def C(self, x):
        return self._add_element_submatrices('C', x, ())

    def U(self, t=0.0):
        return self._add_element_subvectors('U', None, (t,))

    def i(self, x):
        return self._add_element_subvectors('i', x, ())

    def CY(self, x, kT):
        """Calculate composite noise source correlation matrix

        The noise sources in one element are assumed to be uncorrelated with the noise sources in the other elements.

        """
        return self._add_element_submatrices('CY', (x, kT))
        
    def _add_element_submatrices(self, methodname, x, args):
        n=self.n()
        A=zeros((n,n), dtype=object)

        for instance,element in self.elements.items():
            nodemap = self.elementnodemap[instance]
            if x != None:
                subx = x[nodemap,:]
                A[[[i] for i in nodemap], nodemap] += getattr(element, methodname)(subx, *args)
            else:
                A[[[i] for i in nodemap], nodemap] += getattr(element, methodname)(*args)
        return A

    def _add_element_subvectors(self, methodname, x, args):
        n=self.n()
        A=zeros((n,1), dtype=object)

        for instance,element in self.elements.items():
            nodemap = self.elementnodemap[instance]
            if x != None:
                subx = x[nodemap,:]
                A[nodemap,:] += getattr(element, methodname)(subx, *args)
            else:
                A[nodemap,:] += getattr(element, methodname)(*args)
        return A
        
        
class R(Circuit):
    """Resistor element

    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> c['R'] = R(n1, gnd, r=1e3)
    >>> c.G(0)
    array([[0.001, -0.001],
           [-0.001, 0.001]], dtype=object)
    >>> c = SubCircuit()
    >>> n2=c.addNode('2')
    >>> c['R'] = R(n1, n2, r=1e3)
    >>> c.G(0)
    array([[0.001, -0.001],
           [-0.001, 0.001]], dtype=object)

    """
    terminals = ['plus', 'minus']

    def __init__(self, plus, minus, r=1e3):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.parameters['r']=r
        
    def G(self, x):
        g = 1/self.parameters['r']
        return  array([[g, -g],
                        [-g, g]], dtype=object)

    def CY(self, x, kT):
        iPSD = 4*kT/self.parameters['r']
        return  array([[iPSD, -iPSD],
                       [-iPSD, iPSD]], dtype=object)
        

class C(Circuit):
    """Capacitor

    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> c['C'] = C(n1, gnd, c=1e-12)
    >>> c.G(0)
    array([[0, 0],
           [0, 0]], dtype=object)
    >>> c.C(0)
    array([[1e-12, -1e+12],
           [-1e+12, 1e+12]], dtype=object)

    """

    terminals = ['plus', 'minus']    
    def __init__(self, plus, minus, c=0.0):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.parameters['c'] = c

    def C(self, x):
        return array([[self.parameters['c'], -1/self.parameters['c']],
                      [-1/self.parameters['c'], 1/self.parameters['c']]])

class L(Circuit):
    """Inductor

    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> c['C'] = L(n1, gnd, L=1e-9)
    >>> c.G(0)
    array([[0.0, 0.0, 1.0],
           [0.0, 0.0, -1.0],
           [1.0, -1.0, 0.0]], dtype=object)
    >>> c.C(0)
    array([[0, 0, 0],
           [0, 0, 0],
           [0, 0, 1e-09]], dtype=object)
    """
    terminals = ['plus', 'minus']    

    _G = array([[0.0 , 0.0, 1.0],
                [0.0 , 0.0, -1.0],
                [1.0 , -1.0, 0.0]])
    def __init__(self, plus, minus, L=0.0):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.branches.append(Branch(plus, minus))
        self.parameters['L']=L
        
    def G(self, x):
        return self._G
    def C(self, x):
        n = self.n()
        C = zeros((n,n), dtype=object)
        C[-1,-1] = self.parameters['L']
        return C

class VS(Circuit):
    """Independent voltage source

    >>> from analysis import DC
    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> c['vs'] = VS(n1, gnd, v=1.5)
    >>> c['R'] = R(n1, gnd, r=1e3)
    >>> DC(c).solve(refnode=gnd)
    array([[ 1.5   ],
           [ 0.    ],
           [-0.0015]])
    
    """
    terminals = ['plus', 'minus']

    def __init__(self, plus=None, minus=None, v=0.0):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.branches.append(Branch(plus, minus))
        self.parameters['v']=v

    def G(self, x):
        return array([[0.0 , 0.0, 1.0],
                       [0.0 , 0.0, -1.0],
                       [1.0 , -1.0, 0.0]], dtype=object)

    def U(self, t=0.0):
        return array([[0.0, 0.0, -self.parameters['v']]], dtype=object).T

class IS(Circuit):
    """Independent current source

    >>> from analysis import DC, gnd as gnd2
    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> c['is'] = IS(gnd, n1, i=1e-3)
    >>> c['R'] = R(n1, gnd, r=1e3)
    >>> DC(c).solve(refnode=gnd)
    array([[ 1.],
           [ 0.]])
    
    """
    terminals = ['plus', 'minus']

    def __init__(self, plus, minus, i=0.0):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.parameters['i']=i
        
    def U(self, t=0.0):
        return array([[self.parameters['i'], -self.parameters['i']]]).T

class VCVS(Circuit):
    """Voltage controlled voltage source

    >>> from analysis import DC
    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> n2=c.addNode('2')
    >>> c['vs'] = VS(n1, gnd, v=1.5)
    >>> c['vcvs'] = VCVS(n1, gnd, n2, gnd, g=2.0)
    >>> c['vcvs'].nodes
    [Node('2'), Node('gnd'), Node('1')]
    >>> c['vcvs'].branches
    [Branch(Node('2'),Node('gnd'))]
    >>> c['vcvs'].G(0)
    array([[0, 0, 0, 1.0],
           [0, 0, 0, -1.0],
           [0, 0, 0, 0],
           [-1.0, -1.0, 2.0, 0]], dtype=object)
    """
    terminals = ('inp', 'inn', 'outp', 'outn')
    def __init__(self, inp, inn, outp, outn, g=1.0):
        Circuit.__init__(self, inp=inp, inn=inn, outp=outp, outn=outn)
        self.branches.append(Branch(outp, outn))
        self.parameters['g']=g
        
    def G(self, x):
        G = super(VCVS, self).G(x)
        branchindex = -1
        inpindex,innindex,outpindex,outnindex = \
            (self.nodes.index(self.nodenames[name]) for name in ('inp', 'inn', 'outp', 'outn'))
        G[outpindex, branchindex] += 1.0
        G[outnindex, branchindex] += -1.0
        G[branchindex, outpindex] += -1.0
        G[branchindex, outnindex] += 1.0
        G[branchindex, inpindex] += self.parameters['g']
        G[branchindex, innindex] += -self.parameters['g']
        return G

class VCCS(Circuit):
    """Voltage controlled current source

    >>> from analysis import DC
    >>> c = SubCircuit()
    >>> n1=c.addNode('1')
    >>> n2=c.addNode('2')
    >>> c['vs'] = VS(n1, gnd, v=1.5)
    >>> c['vccs'] = VCCS(n1, gnd, n2, gnd, gm=1e-3)
    >>> c['rl'] = R(n2, gnd, r=1e3)
    >>> DC(c).solve(refnode=gnd)
    array([[ 1.5],
           [-1.5],
           [ 0. ],
           [ 0. ]])

    """
    terminals = ['inp', 'inn', 'outp', 'outn']
    
    def __init__(self, inp, inn, outp, outn, gm=1e-3):
        Circuit.__init__(self, inp=inp, inn=inn, outp=outp, outn=outn)

        self.parameters['gm']=gm
        
    def G(self, x):
        G = super(VCCS, self).G(x)
        gm=self.parameters['gm']
        inpindex,innindex,outpindex,outnindex = \
            (self.nodes.index(self.nodenames[name]) for name in ('inp', 'inn', 'outp', 'outn'))
        G[outpindex, inpindex] += gm
        G[outpindex, innindex] += -gm
        G[outnindex, inpindex] += -gm
        G[outnindex, innindex] += gm
        return G

class Diode(Circuit):
    terminals = ['plus', 'minus']
    def __init__(self, plus, minus, IS=1e-6):
        Circuit.__init__(self, plus=plus, minus=minus)
        self.IS = IS
        self.VT = 1.38e-23 * 300 / 1.602e-19
        
    def G(self, x):
        VD = x[0,0]-x[1,0]
        g = self.IS*exp(VD/self.VT)/self.VT
        return array([[g, -g],
                      [-g, g]], dtype=object)

    def i(self, x):
        """
        >>> d = Diode()
        >>> d.i(array([[0., 0.]]).T
        
        """
        VD = x[0,0]-x[1,0]
        I = self.IS*(exp(VD/self.VT)-1.0)
        return array([[I, -I]], dtype=object).T

if __name__ == "__main__":
    import doctest
    doctest.testmod()