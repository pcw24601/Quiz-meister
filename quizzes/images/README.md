# Quiz Images

Place your quiz images in this folder. They will be served at `/quiz-images/filename.ext`.

## Usage in Quiz YAML

In your quiz file, reference images like this:

```yaml
- type: picture
  text: "What famous landmark is this?"
  image: "/quiz-images/eiffel-tower.jpg"
  options:
    - "Statue of Liberty"
    - "Eiffel Tower"
    - "Colosseum"
  correct: 1
  time: 30
  points: 2
```

## Supported Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)

## Organization

You can create subfolders to organize images by round or topic:

```
images/
  round1/
    question1.jpg
    question2.jpg
  round2/
    landmark.png
```

Then reference as: `/quiz-images/round1/question1.jpg`
