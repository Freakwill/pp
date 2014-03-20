"""
anamorphgl.py

An OpenGL program that does anamorphic projection.

Author: Mahesh Venkitachalam
"""

import OpenGL
from OpenGL.GL import *

import numpy, math, sys, os, argparse
import glutils
import Image

import cyglfw3 as glfw

from imagerender import ImageRender

strVS = """
#version 330 core

layout(location = 0) in vec3 aVert;
layout(location = 1) in vec2 aTex;

uniform mat4 uMVMatrix;
uniform mat4 uPMatrix;
uniform float uTheta;
uniform bool showProjection;
uniform vec3 uEye;

out vec2 vTexCoord;
out vec4 vColor;

void main() {

  vec3 P = aVert;
  vColor = vec4(0.0, 1.0, 0.0, 1.0);

  if (showProjection) {
    float R = 1.0;
    vec3 E = uEye;
    vec3 N = vec3(aVert.xy/R, 0.0);
    vec3 I = aVert;
    vec3 d1 = normalize(I-E);
    vec3 d2 = normalize(d1 - 2*dot(d1, N)*N);
    float t = -I.z/d2.z;
    P = I + d2*t;
    vColor = vec4(1.0, 0.0, 0.0, 1.0);
  }

  // transform vertex
  gl_Position = uPMatrix * uMVMatrix * vec4(P, 1.0); 
  // set texture coord
  vTexCoord = vec2(aTex.x, 1-aTex.y);
}
"""
strFS = """
#version 330 core

in vec2 vTexCoord;
in vec4 vColor;

uniform sampler2D tex2D;

out vec4 fragColor;

void main() {
     fragColor = vColor;
     fragColor = texture(tex2D, vTexCoord);
}
"""

class Anamorph:    
    """ OpenGL 3D anamorph class"""
    # initialization
    def __init__(self, params):

        self.params = params
        # window dims
        self.width, self.height = params['winDims']

        # output image dimensions
        self.imgWidth, self.imgHeight = params['imgDims']
        
        self.aspect = 1.0
        # create shader
        self.program = glutils.loadShaders(strVS, strFS)

        # define triange strip vertices 
        R = params['r']
        nR = 100
        H = params['hCyl']
        nH = 100     
        vertexData = numpy.zeros(3*nR*nH, numpy.float32).reshape(nR*nH, 3)
        texData = numpy.zeros(2*nR*nH, numpy.float32).reshape(nR*nH, 2)
        # angles
        tStart = math.pi/2.0 - params['theta']
        tEnd = math.pi/2.0 + params['theta']
        angles = numpy.linspace(tStart, tEnd, nR)
        heights = numpy.linspace(0, H, nH)
        i = 0
        for h in heights:
            for t in angles:
                x = R*math.cos(t)
                y = R*math.sin(t)
                z = h
                tx = t/math.pi
                ty = h/H
                vertexData[i] = [x, y, z]
                texData[i] = [tx, ty]
                i += 1
        vertexData.resize(3*nR*nH, 1)
        texData.resize(2*nR*nH, 1)
    
        #print vertexData
        #print texData

        # set up vertex array object (VAO)
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        # vertices
        self.vertexBuffer = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertexBuffer)
        # set buffer data 
        glBufferData(GL_ARRAY_BUFFER, 4*len(vertexData), vertexData, 
                     GL_STATIC_DRAW)
        # enable vertex array
        glEnableVertexAttribArray(0)
        # set buffer data pointer
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)

        # texture coords
        texBuffer = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, texBuffer)
        # set buffer data 
        glBufferData(GL_ARRAY_BUFFER, 4*len(texData), texData, 
                     GL_STATIC_DRAW)
        # enable vertex array
        glEnableVertexAttribArray(1)
        # set buffer data pointer
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, None)

        # index buffer
        indices = []
        index = 0
        for j in range(nH-1):
            for i in range(nR):
                # repeat first vertex
                if j > 0 and i is 0:
                    indices.append(index)
                indices.append(index)
                indices.append(index+nR)
                # repeat last vertex - except for absolute last
                if i is nR-1:
                    indices.append(index+nR)
                index += 1
        indexData = numpy.array(indices, numpy.int16)
        self.nIndices = len(indices)
         
        #print indexData
        
        # index buffer
        self.indexBuffer = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.indexBuffer);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, 2*len(indexData), indexData, 
                     GL_STATIC_DRAW)
        # index
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.indexBuffer)
    

        # unbind VAO
        glBindVertexArray(0)

        # time
        self.t = 0 

        # texture
        self.texId = glutils.loadTexture(params['file'])

        self.showCylinder = True
        
        # create image render object
        self.ir = ImageRender(self.imgWidth, self.imgHeight, GL_TEXTURE1)

    # step
    def step(self):
        # increment angle
        self.t = (self.t + 1) % 360
        # set shader angle in radians
        glUniform1f(glGetUniformLocation(self.program, 'uTheta'), 
                    math.radians(self.t))

    # save to image
    def renderToImage(self, imgFile):
        self.ir.bind()
        glViewport(0, 0, self.imgWidth, self.imgHeight)
        glEnable(GL_DEPTH_TEST)
        self.render()
        self.ir.saveImage(imgFile)
        self.ir.unbind()
        self.ir.close()
        glViewport(0, 0, self.width, self.height)

    # render 
    def render(self):     

        # clear
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # build projection matrix
        pMatrix = glutils.perspective(45.0, self.aspect, 0.1, 100.0)

        R = self.params['R']
        pMatrix = glutils.ortho(-R, R, -R, R, 0.1, 100.0)

        #mvMatrix = glutils.lookAt([0.0, 4.0, 8.0], [0.0, 2.0, 2.0],
        #                          [0.0, -1.0, 0.0])

        mvMatrix = glutils.lookAt([0.0, 0.0, -15.0], [0.0, 0.0, 0.0],
                                  [1.0, 0.0, 0.0])

        mvMatrix = glutils.translate(0.0, 0.0, -15.0)

        """
        pMatrix = glutils.ortho(*self.params['ortho'])

        pMatrix = glutils.ortho(0.2050109578077233, 6.120701299694291, 
                                -3.4934772684871156, 3.4934772684871156, 
                                0.1, 100.0)
         mvMatrix = glutils.lookAt([0.0, 0.0, -20.0], [0.0, 0.0, 0.0],
                                  [0.0, 1.0, 0.0])

        """
        # use shader
        glUseProgram(self.program)
        
        # set proj matrix
        glUniformMatrix4fv(glGetUniformLocation(self.program, 'uPMatrix'), 
                           1, GL_FALSE, pMatrix)

        # set modelview matrix
        glUniformMatrix4fv(glGetUniformLocation(self.program, 
                                                "uMVMatrix"), 
                           1, GL_FALSE, mvMatrix)

        # set eye
        eye = self.params['eye']
        glUniform3f(glGetUniformLocation(self.program, 'uEye'),
                    eye[0], eye[1], eye[2])
        
        # enable texture 
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texId)
        glUniform1i(glGetUniformLocation(self.program, "tex2D"), 0)

        # bind VAO
        glBindVertexArray(self.vao)

        # draw cylinder
        if self.showCylinder:
            glUniform1i(glGetUniformLocation(self.program, 'showProjection'), 
                        False)
            glDrawElements(GL_TRIANGLE_STRIP, self.nIndices, 
                           GL_UNSIGNED_SHORT, None)
        
        # draw projection
        glUniform1i(glGetUniformLocation(self.program, 'showProjection'), 
                    True)
        glDrawElements(GL_TRIANGLE_STRIP, self.nIndices, 
                       GL_UNSIGNED_SHORT, None)
        
        # unbind VAO
        glBindVertexArray(0)


class RenderWindow:
    """GLFW Rendering window class"""
    def __init__(self, params):

        # save current working directory
        cwd = os.getcwd()

        # initialize glfw - this changes cwd
        glfw.Init()
        
        # restore cwd
        os.chdir(cwd)

        # version hints
        glfw.WindowHint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.WindowHint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.WindowHint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
        glfw.WindowHint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    
        # make a window
        self.width, self.height = params['winDims']
        self.aspect = self.width/float(self.height)
        self.win = glfw.CreateWindow(self.width, self.height, "anamorphic")
        # make context current
        glfw.MakeContextCurrent(self.win)
        
        # initialize GL
        glViewport(0, 0, self.width, self.height)
        glEnable(GL_DEPTH_TEST)
        glClearColor(1.0, 1.0, 1.0, 1.0)

        # set window callbacks
        glfw.SetMouseButtonCallback(self.win, self.onMouseButton)
        glfw.SetKeyCallback(self.win, self.onKeyboard)
        glfw.SetWindowSizeCallback(self.win, self.onSize)        

        # create 3D
        self.anamorph = Anamorph(params)
        self.anamorph.aspect = self.aspect

        # exit flag
        self.exitNow = False

        
    def onMouseButton(self, win, button, action, mods):
        #print 'mouse button: ', win, button, action, mods
        pass

    def onKeyboard(self, win, key, scancode, action, mods):
        #print 'keyboard: ', win, key, scancode, action, mods
        if action == glfw.PRESS:
            # ESC to quit
            if key == glfw.KEY_ESCAPE: 
                self.exitNow = True
            elif key == glfw.KEY_P:
                print 'saving...'
                self.anamorph.renderToImage('test.png')
            else:
                self.anamorph.showCylinder = not self.anamorph.showCylinder
        
    def onSize(self, win, width, height):
        #print 'onsize: ', win, width, height
        self.width = width
        self.height = height
        self.aspect = width/float(height)
        self.anamorph.aspect = self.aspect
        glViewport(0, 0, self.width, self.height)

    def run(self):
        # initializer timer
        glfw.SetTime(0.0)
        t = 0.0
        while not glfw.WindowShouldClose(self.win) and not self.exitNow:
            # update every x seconds
            currT = glfw.GetTime()
            if currT - t > 0.1:
                # update time
                t = currT
                # render
                self.anamorph.render()
                # step 
                self.anamorph.step()

                glfw.SwapBuffers(self.win)
                # Poll for and process events
                glfw.PollEvents()
        # end
        glfw.Terminate()

# main() function
def main():
    print 'starting anamorphic...'  

    # create parser
    parser = argparse.ArgumentParser(description="Anamorphic Projection...")
    # add expected arguments
    parser.add_argument('--file', dest='imgFile', required=True)
    parser.add_argument('--r', dest='radius', required=False)
    parser.add_argument('--h', dest='height', required=False)
    parser.add_argument('--d', dest='dist', required=False)
    # parse args
    args = parser.parse_args()
    
    # parameters in a dictionary
    params = {}
    params['file'] = args.imgFile
    radius, height, dist = 1.0, 3.0, 4.0
    if args.radius:
        radius = float(args.radius)
    if args.height:
        height = float(args.height)
    if args.dist:
        dist = float(args.dist)

    # inputs
    params['r'] = radius
    Ey = dist
    Ez = height    
    params['eye'] = [0.0, Ey, Ez]
    # get tex image dims
    texImg = Image.open(args.imgFile)
    texW, texH = texImg.size 
    # compute image height on cylinder
    theta = math.acos(radius/Ey)
    params['theta'] = theta
    print math.degrees(theta)
    hCyl = (2.0*theta*radius)*texH/float(texW)

    # compute projection parameters
    R = abs(radius + hCyl*Ey/float(Ez-hCyl))
    params['R'] = R 
    params['hCyl'] = hCyl
    params['winDims'] = (700, 700)
    #params['imgDims'] = (int(300*2*R), int(300*2*R))
    params['imgDims'] = (1024, 1024)

    print params

    rw = RenderWindow(params)
    rw.run()

# call main
if __name__ == '__main__':
    main()