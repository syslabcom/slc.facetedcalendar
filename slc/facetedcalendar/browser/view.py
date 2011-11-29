from zope.app.component.hooks import getSite
from Acquisition import aq_inner
from Products.ATContentTypes.interfaces import IATTopic

from Solgema.fullcalendar.browser.solgemafullcalendar_views import \
                                                    SolgemaFullcalendarView
from Solgema.fullcalendar.browser.solgemafullcalendar_views import \
                                                    SolgemaFullcalendarEvents
                                                    
from ZODB.POSException import ConflictError
from Products.ZCTextIndex.ParseTree import ParseError
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.browser.navtree import getNavigationRoot

class FacetedCalendarView(SolgemaFullcalendarView):
    """ """

    def queryCatalog(self, **kwargs):
    
        context = aq_inner(self.context)
        # XXX: Must rather look for a way to use the Topic's query itself.
        if IATTopic.providedBy(context):
            context = context.aq_parent
        self.request.set('facet', 'true')
        self.request.set('facet.field', ['SearchableText', 'review_state', 'portal_type', 'start', 'end'])
        self.request.set('path', '/'.join(context.getPhysicalPath()))
        # We must ensure that we're not on a Topic when
        # acquiring the queryCatalog. We want the controller python script, not
        # the Topic method.
        site = getSite()
        results = self.queryCatalogx(**kwargs)
        return results

    def queryCatalogx(
                self,
                REQUEST,
                show_all=0,
                quote_logic=0,
                quote_logic_indexes=['SearchableText','Description','Title'],
                use_types_blacklist=False,
                show_inactive=False,
                use_navigation_root=False,
                b_start=None,
                b_size=None):

        results=[]
        context = aq_inner(self.context)
        catalog=context.portal_catalog
        indexes=catalog.indexes() + quote_logic_indexes
        query={}
        show_query=show_all
        second_pass = {}

        def quotestring(s):
            return '"%s"' % s

        def quotequery(s):
            if not s:
                return s
            try:
                terms = s.split()
            except ConflictError:
                raise
            except Exception:
                return s
            tokens = ('OR', 'AND', 'NOT')
            s_tokens = ('OR', 'AND')
            check = (0, -1)
            for idx in check:
                if terms[idx].upper() in tokens:
                    terms[idx] = quotestring(terms[idx])
            for idx in range(1, len(terms)):
                if (terms[idx].upper() in s_tokens and
                    terms[idx-1].upper() in tokens):
                    terms[idx] = quotestring(terms[idx])
            return ' '.join(terms)

        # We need to quote parentheses when searching text indices (we use
        # quote_logic_indexes as the list of text indices)
        def quote_bad_chars(s):
            bad_chars = ["(", ")"]
            for char in bad_chars:
                s = s.replace(char, quotestring(char))
            return s

        def ensureFriendlyTypes(query):
            ploneUtils = getToolByName(context, 'plone_utils')
            portal_type = query.get('portal_type', [])
            if type(portal_type) != list:
                portal_type = [portal_type]
            Type = query.get('Type', [])
            if type(Type) != list:
                Type = [Type]
            typesList = portal_type + Type
            if not typesList:
                friendlyTypes = ploneUtils.getUserFriendlyTypes(typesList)
                query['portal_type'] = friendlyTypes

        def rootAtNavigationRoot(query):
            if 'path' not in query:
                query['path'] = getNavigationRoot(context)

        # Avoid creating a session implicitly.
        for k in REQUEST.keys():
            if k == 'SESSION':
                continue
            v = REQUEST.get(k)
            if v and k in indexes:
                if k in quote_logic_indexes:
                    v = quote_bad_chars(v)
                    if quote_logic:
                        v = quotequery(v)
                query[k] = v
                show_query = 1
            elif k.endswith('_usage'):
                key = k[:-6]
                param, value = v.split(':')
                second_pass[key] = {param: value}
            elif k in ('sort_on', 'sort_order', 'sort_limit'):
                if k == 'sort_limit' and type(v) != int:
                    query[k] = int(v)
                else:
                    query[k] = v
            elif k in ('fq', 'fl', 'facet', 'b_start', 'b_size') or k.startswith('facet.'):
                query[k] = v

        for k, v in second_pass.items():
            qs = query.get(k)
            if qs is None:
                continue
            query[k] = q = {'query': qs}
            q.update(v)

        if b_start is not None:
            query['b_start'] = b_start
        if b_size is not None:
            query['b_size'] = b_size

        query['use_solr'] = True

        # doesn't normal call catalog unless some field has been queried
        # against. if you want to call the catalog _regardless_ of whether
        # any items were found, then you can pass show_all=1.
        if show_query:
            try:
                if use_types_blacklist:
                    ensureFriendlyTypes(query)
                if use_navigation_root:
                    rootAtNavigationRoot(query)
                query['show_inactive'] = show_inactive
                results = catalog(**query)
            except ParseError:
                pass

        return results

