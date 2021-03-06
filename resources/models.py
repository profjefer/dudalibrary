# -*- coding: utf-8 -*-
from django.utils.encoding import smart_str
import datetime, os, subprocess, urllib2, time
from django.db import models
from django.utils.translation import ugettext_lazy as _
from options.models import Category, Language, Source, Device
from django.db.models.signals import pre_save
from dudalibrary.utils import *
from PIL import Image
import tagging
from tagging.fields import TagField

from django.conf import settings

try: 
    import json
except ImportError:
    # python 2.5
    import simplejson

STATUS_CHOICES = (
    ('installed', _('Installed resource')),
    ('processing', _('Processing...')),
    ('queue', _('Queued. Content is on queue')),
    ('downloaded', _('Downloaded...')),
    ('rejected', _('Rejected. Not indexable')),
    ('error', _('Error. Not indexed')),
)

class Resource(models.Model):
    '''This is a Model to store the Education Resource'''
    
    class Meta:
        ordering = ['-featured','-pageviews', '-resource_pageviews', '-thumbnails']
        #unique_together = (("resource_reference_string", "source"),)
    
    def __unicode__(self):
        return '%s' % self.title
    
    # resource identifier
    resource_reference_string = models.CharField(blank=True, max_length=500)
    # global resource identificator
    globalid = models.CharField(blank=True, null=True, help_text=_("This is for Custom Resources Only. Its the part for globalid@yourdomain.com"), max_length=100)
    custom_resource = models.BooleanField(default=False)
    # enabled, featured, etc
    enabled = models.BooleanField(default=False)
    featured = models.BooleanField(default=False, verbose_name=_("Featured"),)
    # general information
    title = models.CharField(blank=True, max_length=800, verbose_name=_("Title"))
    structure = models.TextField(blank=True, verbose_name=_("Strucutre"))
    objective = models.TextField(blank=True, verbose_name=_("General objectives"))
    description = models.TextField(blank=True, verbose_name=_("General description"))
    author = models.TextField(blank=True, verbose_name=_("Authors"), help_text=_("One per line"))
    notes = models.TextField(blank=True, verbose_name=_("Additional notes"))
    content_source = models.TextField(blank=True, verbose_name=_("Content Source"))
    license = models.TextField(blank=True, verbose_name=_("License"), help_text=_("Known license"))
    published = models.DateField(default=datetime.datetime.today, verbose_name=_("Published date"))
    size = models.CharField(blank=True, max_length=100, verbose_name="Size in bytes")
    pageviews = models.IntegerField(blank=True, null=True, default=0)
    trigger = models.CharField(blank=True, max_length=400, verbose_name=_("Trigger"), help_text="Resource execution trigger")
    trigger_extension = models.CharField(blank=True, max_length=100)
    thumbnails = models.IntegerField(blank=True, null=True, default=0, verbose_name=_("Number of thumbnails"))
    duration = models.IntegerField(blank=True, null=True, default=0)
    # resource original information
    resource_url = models.URLField(blank=True, max_length=400, help_text="Resource url origin")
    resource_download_url = models.URLField(blank=True, max_length=800)
    resource_downloaded_file = models.CharField(blank=True, max_length=800)
    resource_size = models.CharField(blank=True, max_length=100)
    resource_pageviews = models.IntegerField(blank=True, null=True)
    resource_language = models.CharField(blank=True, max_length=300, null=True)
    tags = TagField(max_length=400)
    # foreign information
    source = models.ForeignKey(Source, blank=False, null=False)
    language = models.ForeignKey(Language, blank=True, null=True)
    category = models.ManyToManyField(Category, blank=True, null=True)
    main_category = models.ForeignKey(Category, related_name="main_category_resource_set")
    device = models.ManyToManyField(Device, blank=True, null=True)
    # system information
    status = models.CharField(blank=True, max_length=100, choices=STATUS_CHOICES, help_text="Operational status")
    version = models.IntegerField(blank=True, null=True, help_text="Actual version of the content")
    # metadata information
    created = models.DateTimeField(blank=True, default=datetime.datetime.now, auto_now_add=True)
    updated = models.DateTimeField(blank=True, default=datetime.datetime.now, auto_now=True)
    zip_md5 = models.CharField(blank=True, max_length=300)
    # GLOBAL SERVER ONLY TODO: manage better upgrades
    #updated_flag = models.BooleanField(default=False)
    
    def category_code_set(self):
        return set(self.category.all().values_list('code', flat=True))

    def humanized_duration(self):
        if 'video' in self.category_code_set():
            # in seconds
            output = time.strftime('%H:%M:%S', time.gmtime(self.duration))
            bits = output.split(":")
            if bits[0] == '00':
                output = ":".join(bits[1:3])
        elif 'ebook' in self.category_code_set():
            # in pages
            output = "%d pages" % self.duration
        else:
            output = self.duration
        return output
    
    def app_label(self):
        return self._meta.app_label
    
    def module_name(self):
        return self._meta.module_name
    
    @models.permalink
    def get_absolute_url(self):
        return ('resource_details', (), 
            {
            'object_id': str(self.id),
            }
        )

    def content_url(self):
        return u"%s/%s/%s/%s" % (settings.CONTENT_URL, str(self.source.slug.lower()), self.resource_reference_string, self.trigger)

    def content_url_path(self):
        return u"%s/%s/%s/" % (settings.CONTENT_URL, str(self.source.slug.lower()), self.resource_reference_string)

    def content_root(self):
        path = u"%s/%s/%s/%s" % (str(settings.CONTENT_ROOT), str(self.source.slug.lower()), str(self.resource_reference_string), str(self.trigger))
        # necessary to decode things like %20, %28...
        return urllib2.unquote(path)
        
    def content_root_path(self):
        return u"%s/%s/%s/" % (settings.CONTENT_ROOT, str(self.source.slug.lower()), self.resource_reference_string)

    def create_content_root(self):
        if not os.path.exists(self.content_root()):
          os.makedirs(self.content_root())

    def repository_url(self):
        # considers the size of the ID digits.
        # different handles for 0-9 and >=10
        if len(str(self.id)) > 1:
            return u'%s/%s/%s/%d/%d/%s.zip' % (settings.REPOSITORY_URL, str(self.source.slug.lower()), self.language.code, int(str(self.id)[-1]), int(str(self.id)[-2]), self.reference_string)
        else:
            return u'%s/%s/%s/%d/%s.zip' % (settings.REPOSITORY_URL, str(self.source.slug.lower()), self.language.code, int(str(self.id)[-1]), self.id)

    def repository_root(self):
        if len(str(self.id)) > 1:
            return u'%s/%s/%s/%d/%d/%s.zip' % (settings.REPOSITORY_ROOT, str(self.source.slug.lower()), self.language.code, int(str(self.id)[-1]), int(str(self.id)[-2]), self.reference_string)
        else:
            return u'%s/%s/%s/%d/%s.zip' % (settings.REPOSITORY_ROOT, str(self.source.slug.lower()), self.language.code, int(str(self.id)[-1]), self.id)

    def thumbnails_path(self):
        thumbs = []
        if self.thumbnails == 0:
            thumbs.append("%ssite_media/img/icons/thumb-placeholder.png" % settings.STATIC_URL)
        else:
            base_url = settings.CONTENT_URL
            for t in range(1,int(self.thumbnails)+1):
                t_path = "%s/thumbnail%d.jpg" % (self.content_url_path(), t)
                thumbs.append(t_path)
        return thumbs

    def size_humanized(self):
        if self.size != 0:
            out = human_size(int(self.size))
            return out
            #return "%0.1f MB" % (int(self.size)/(1024*1024.0))
        else:
            return self.size

    def force_tags(self, tags):
        tags = r.structure.strip()
        tags = tags.replace('|', ',').replace('::', ',').replace(':', ','
            ).replace('/', ',').replace(" e ", ',').replace('\n', ',')
        tags = tags.split(',')
        tags = [t.strip().capitalize() for t in tags]
        tags = ",".join(tags)
        # eliminate duplicates
        tags = parse_tag_input(tags)
        # get it back to value,value,value
        good_tags = []
        for i in range(0,len(tags)):
            good_tags.append(tags[i])
            try:
                r.tags = good_tags
                r.save()
            except:
                good_tags.pop()
        r.tags = ",".join(good_tags)
        r.save()

    def generate_descriptor(self, force=False):
        try:
            workdir = os.path.dirname(self.content_root_path())
            if not os.path.exists(workdir):
                subprocess.call("mkdir -vp %s" % workdir, shell=True)

            descriptor_file = "%s/descriptor.xml" % workdir
            if os.path.exists(descriptor_file) and force or not os.path.exists(descriptor_file):
                stream = open(descriptor_file, "w")
                # serialize n write outfile on it
                fields = []
                for field in self._meta.fields:
                    fields.append(field.name)
                # remove unwanted fields
                outfields = ['zip_md5','pageviews', 'status', 'updated', ]
                for outfield in outfields:
                    fields.remove(outfield)
                print "Creating descriptor for %s (%s) in  %s" % (self, self.id, smart_str(self.content_root_path()))
                data = serializers.serialize('xml', [ self, ], fields=fields, stream=stream)
                return True
            else:
                print "Warning: File Descriptor not Generated for Resource ID: %s" % self.id
                return False
        except:
            raise
            return False
    
    def generate_pack(self, force=True):
        '''force=False will only generate the missing ones'''
        try:
            self.generate_descriptor(force)
            outfolder = os.path.dirname(self.repository_root())
            outfile = self.repository_root()
            if not os.path.exists(self.repository_root()) or force:
                print "Creating pack of GRID-%s" % self.pk
                #  unsure path exist
                path = os.path.dirname(self.repository_root())
                if not os.path.exists(path):
                    subprocess.call("mkdir -vp %s" % path, shell=True)
                zipdir(os.path.dirname(self.content_root_path()), self.repository_root())
            else:
                print u"GRID-%s is packed already: %s" % (self.pk, self.repository_root())
            return True
        except:
            raise
            return False

    def generate_thumb(self, quantidade=8, thumbnail_size="cif", deleteold=True):
        extension_to_screenshot = ('wmv', 'flv', 'avi', 'mov', 'mpg', 'mp4', 'vob', 'webm')
        if os.path.isfile(smart_str(self.content_root())) and self.trigger.split(".")[-1].lower() in extension_to_screenshot:
            seconds = getLength(self.content_root())
            dest = os.path.dirname(self.content_root())
            extension = self.trigger.split(".")[-1].lower()
            # ffmpegthumbnailer is way better... let it try first
            if find_program_path('ffmpegthumbnailer'):
                frames_percentage = range(0,100,100/quantidade)[1:]
                i = 1
                for frame in frames_percentage:
                    thumb_name = "thumbnail%d.jpg" % int(i)
                    i += 1
                    if deleteold == False and os.path.isfile("%s/%s" % (dest, thumb_name)):
                        print "Not deleting or overwriting %s" % thumb_name
                    else:
                        print "Using ffmpegthumbnailer"  
                        screenshot_command = 'ffmpegthumbnailer -i "%s" -o "%s/%s" -s 300 -a -t %s' \
                            % (self.content_root(), dest, thumb_name, frame)
                    #screenshot_command = "ffmpeg -i '%s' %s -f image2 -ss %d -sameq -t 1 -s %s %s/%s " % \
                    #    (self.content_root(), deleteold_arg, secs_maps[img], thumbnail_size, dest, thumb_name)
                        print "Comando:",screenshot_command
                        subprocess.call(smart_str(screenshot_command), shell=True)
                
                
            else:
                if not seconds:
                    seconds = 60
                trigger = self.trigger
                # steps to range, so it grabs distributed screenshots
                seconds_step = seconds / quantidade - 3
                # too short video, only 3 thumbnails
                if seconds_step <= 0:
                    quantidade = 3
                    seconds_step = seconds / quantidade
                secs_maps = range(5,seconds-5, seconds_step)
                if seconds <= 40:
                    quantidade = 4
                    secs_maps = (1, 10, 20, 25, 35)        
                if seconds <= 10:
                    quantidade = 1
                    secs_maps = (1, 2, 3, 4, 5)
                deleteold_arg = ''
                if deleteold == True:
                    deleteold_arg = '-y'
                    ls = os.listdir(dest)
                    for f in ls:
                        if "thumbnail" in f:
                            cmd = "rm -v %s/%s" % (dest, f)
                            subprocess.call(cmd, shell=True)
                if self.trigger.split(".")[-1].lower() in extension_to_screenshot:
                    for img in range(1,quantidade+1):
                        thumb_name = "thumbnail%d.jpg" % int(img)
                        if deleteold == False and os.path.isfile("%s/%s" % (dest, thumb_name)):
                            print "Not deleting or overwriting %s" % thumb_name
                        else:
                            screenshot_command = "ffmpeg -i '%s' %s -f image2 -ss %d -sameq -t 1 -s %s %s/%s " % \
                                (self.content_root(), deleteold_arg, secs_maps[img], thumbnail_size, dest, thumb_name)
                            print "Comando:",screenshot_command
                            subprocess.call(smart_str(screenshot_command), shell=True)
                else:
                    search_on_folder = True
                    print "Can't thumbnail this file!"
            #count thumbs and add to DB
            files_count = 0
            ls = os.listdir(dest)
            for f in ls:
                if "thumbnail" in f:
                    files_count = int(files_count) + 1
            self.thumbnails = files_count
            self.duration = seconds
            self.save()
            
        else:
            print "File not found or can't thumbnail! %s" % self.content_root()
    
    def content_file_list(self):
        file_list = []
        for root, subFolders, files in os.walk(self.content_root_path()):
            for file in files:
                f = os.path.join(root,file)
                file_list.append(f)
        return file_list
    
    def check_files(self):
        '''check if trigger file can be found on filesystem'''        
        try:
            if os.path.isfile(self.content_root()) == True:
                self.status = 'installed'
                self.save()
                return True
            # lets search...
            for file_item in self.content_file_list():
                if urllib2.unquote(self.trigger) in file_item:
                    self.trigger = file_item.replace(self.content_root_path(), "")
                    self.save()
                    return True
            #maybe its only a file, same as downloaded
            dlfile = "%s/%s" % (self.content_root_path(), self.resource_downloaded_file)
            if os.path.isfile(dlfile) == True:
                self.trigger = self.resource_downloaded_file
                self.save()
                return True
            # what about one file with same exension?
            findings = []
            for file_item in self.content_file_list():
                if self.extension == file_item.rsplit('.')[-1]:
                    findings.append(file_item)
            if len(findings) == 1:
                self.trigger = findings[0].replace(self.content_root_path(), "")
                self.save()
                return True
            else:
                self.enabled = False
                return False
        except:
            self.status = 'error'
            self.enabled = False
            self.save()
            return False



# tagging conf
tagging.register(Resource, tag_descriptor_attr="tag_handler")