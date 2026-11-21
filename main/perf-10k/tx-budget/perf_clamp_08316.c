/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08316(unsigned int count)
{
    const unsigned int limit = 197u;
    return count > limit ? limit : count;
}
