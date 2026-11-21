/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04468(unsigned int count)
{
    const unsigned int limit = 19u;
    return count > limit ? limit : count;
}
