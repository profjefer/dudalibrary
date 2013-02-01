from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', include(admin.site.urls)),
)

from django.conf.urls.defaults import patterns, include, url
from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from frontend.views import TopHitsView, TopVotesView

admin.autodiscover()

urlpatterns += patterns('',
    url(r'^$', 'frontend.views.index', name='index'),
    url(r'^i18n/', include('django.conf.urls.i18n')),    
    (r'^ratings/', include('ratings.urls')),
    url(r'^logout/$',
        'django.contrib.auth.views.logout',
        name='auth_logout'),
    url(r'^add_custom/$',
        'frontend.views.add_custom',
        name='add_custom_resource_url'),
    url(r'^ajax/hit/$', 'hitcount.views.update_hit_count_ajax',
        name='hitcount_update_ajax'),
    )

urlpatterns += i18n_patterns('',
    url(_(r'^random/$'), 'frontend.views.get_random_resource', name='get_random_resource_url'),
    url(_(r'^most/viewed'), TopHitsView.as_view(), name="top_viewed"),
    url(_(r'^most/voted'), TopVotesView.as_view(), name="top_voted"),
    url(_(r'^activity/(?P<object_id>\d+)/$'), 'frontend.views.activity_details', name="activity_details"),
    url(_(r'^activity/(?P<object_id>\d+)/request_resource/$'), 'frontend.views.activity_details_request_resource', name="activity_details_request_resource"),
    url(_(r'^curricular/(?P<object_id>\d+)/'), 'frontend.views.get_curricular_grade', name="curricular_grade"),
    url(_(r'^resource/tag/(?P<pk>[^/]+)/$'), 'frontend.views.tag_details', name="tag_details"),
    url(_(r'^resource/(?P<object_id>\d+)/'), 'frontend.views.resource_details', name="resource_details"),
    url(_(r'^search/'), include('haystack.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
    # CONTENT MEDIA
    url(r'^media/(.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT}),
    )
    url(r'^static/(.*)$', 'django.views.static.serve',
        {'document_root': settings.STATIC_ROOT }
    ),
    