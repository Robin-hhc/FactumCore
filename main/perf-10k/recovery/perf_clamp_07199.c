/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07199(unsigned int count)
{
    const unsigned int limit = 132u;
    return count > limit ? limit : count;
}
