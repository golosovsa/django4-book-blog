from django.core.mail import send_mail
from django.db.models import Count
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import ListView
from django.views.decorators.http import require_POST
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from taggit.models import Tag

from .forms import EmailPostForm, CommentForm, SearchForm
from .models import Post


def post_share(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk, status=Post.Status.PUBLISHED)
    sent = False
    if request.method == 'POST':
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cleaned_data['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n" \
                      f"{cleaned_data['name']}'s comments: {cleaned_data['comments']}"
            send_mail(subject, message, 'golosov_sa@mail.ru', [cleaned_data['to']])
            sent = True
    else:
        form = EmailPostForm()

    return render(request, 'blog/post/share.html', {
        'post': post,
        'form': form,
        'sent': sent,
    })


class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    paginate_by = 3
    template_name = 'blog/post/list.html'


def post_list(request, tag_slug=None):
    posts_list = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        posts_list = posts_list.filter(tags__in=[tag])
    paginator = Paginator(posts_list, 3)
    page_number = request.GET.get('page', 1)
    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    return render(request, 'blog/post/list.html', {'posts': posts, 'tag': tag})


def post_detail(request, year, month, day, slug):
    post = get_object_or_404(
        Post,
        status=Post.Status.PUBLISHED,
        slug=slug,
        publish__year=year,
        publish__month=month,
        publish__day=day,
    )

    post_tags_pks = post.tags.values_list('pk', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_pks).exclude(pk=post.pk)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish')[:4]

    comments = post.comments.filter(active=True)
    form = CommentForm()

    return render(request, 'blog/post/detail.html', {
        'post': post,
        'comments': comments,
        'form': form,
        'similar_posts': similar_posts
    })


@require_POST
def post_comment(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk, status=Post.Status.PUBLISHED)
    comment = None
    form = CommentForm(data=request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.save()
    return render(request, 'blog/post/comment.html', {
        'post': post,
        'form': form,
        'comment': comment
    })


def post_search(request):
    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        # if form.is_valid():
        #     query = form.cleaned_data['query']
        #     search_vector = SearchVector('title', weight='A') + SearchVector('body', weight='B')
        #     search_query = SearchQuery(query)
        #     results = Post.published.annotate(
        #         search=search_vector,
        #         rank=SearchRank(search_vector, search_query),
        #     ).filter(rank__gte=0.3).order_by('-rank')

        if form.is_valid():
            query = form.cleaned_data['query']
            results = Post.published.annotate(
                similarity=TrigramSimilarity('title', query),
            ).filter(similarity__gt=0.1).order_by('-similarity')

    return render(request, 'blog/post/search.html', {
        'form': form,
        'query': query,
        'results': results,
    })
