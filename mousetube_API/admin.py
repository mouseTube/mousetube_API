'''
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''

from django.contrib import admin

from .models import *

admin.site.register(UserProfile)
admin.site.register(Contact)
admin.site.register(Reference)
admin.site.register(Species)
admin.site.register(Strain)
admin.site.register(ProtocolType)
admin.site.register(Protocol)
admin.site.register(Experiment)
admin.site.register(Animal)
admin.site.register(File)
admin.site.register(Software)