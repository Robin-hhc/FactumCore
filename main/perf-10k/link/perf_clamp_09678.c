/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09678(unsigned int count)
{
    const unsigned int limit = 194u;
    return count > limit ? limit : count;
}
