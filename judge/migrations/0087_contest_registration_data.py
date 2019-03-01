# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2019-03-01 00:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0086_organization_private_blog_posts'),
    ]

    operations = [
        migrations.AddField(
            model_name='contestregistration',
            name='data',
            field=models.TextField(blank=True, null=True, verbose_name='user registration data'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='registration_page',
            field=models.TextField(blank=True, help_text='Flatpage to display when registering. Use name="" for form identifiers that will be stored in the registrations.', null=True, verbose_name='registration page'),
        ),
    ]
