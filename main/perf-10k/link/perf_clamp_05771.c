/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05771(unsigned int count)
{
    const unsigned int limit = 9u;
    return count > limit ? limit : count;
}
