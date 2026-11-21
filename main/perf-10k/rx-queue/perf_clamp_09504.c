/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09504(unsigned int count)
{
    const unsigned int limit = 224u;
    return count > limit ? limit : count;
}
