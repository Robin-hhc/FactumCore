/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06524(unsigned int count)
{
    const unsigned int limit = 111u;
    return count > limit ? limit : count;
}
